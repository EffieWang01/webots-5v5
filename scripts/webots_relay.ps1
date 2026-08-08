$ErrorActionPreference = 'Stop'

$source = @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace WebotsFiveVFive
{
    public static class Relay
    {
        private const int StatePort = 10081;
        private const int CommandPort = 10082;
        private const int RelayPort = 10083;
        private static readonly object ClientsLock = new object();
        private static readonly object GatewayLock = new object();
        private static readonly object CommandLock = new object();
        private static readonly List<TcpClient> Clients = new List<TcpClient>();
        private static readonly Regex CommandFrame = new Regex("\\\"type\\\"\\s*:\\s*\\\"robot_command\\\"", RegexOptions.Compiled);
        private static readonly Regex StatusFrame = new Regex("\\\"type\\\"\\s*:\\s*\\\"bridge_status\\\"", RegexOptions.Compiled);
        private static UdpClient stateSocket;
        private static UdpClient commandSocket;
        private static IPEndPoint gatewayAddress;

        public static void Run()
        {
            stateSocket = new UdpClient(new IPEndPoint(IPAddress.Loopback, StatePort));
            commandSocket = new UdpClient(AddressFamily.InterNetwork);
            TcpListener server = new TcpListener(IPAddress.Loopback, RelayPort);
            server.Start(8);

            Console.WriteLine("[RELAY] Webots UDP state :{0}; commands -> :{1}; WSL TCP :{2}", StatePort, CommandPort, RelayPort);

            Thread acceptThread = new Thread(delegate() { AcceptLoop(server); });
            acceptThread.IsBackground = true;
            acceptThread.Start();

            while (true)
            {
                IPEndPoint sender = new IPEndPoint(IPAddress.Any, 0);
                byte[] packet = stateSocket.Receive(ref sender);
                lock (GatewayLock) { gatewayAddress = sender; }
                Broadcast(packet);
            }
        }

        private static void AcceptLoop(TcpListener server)
        {
            while (true)
            {
                TcpClient client = server.AcceptTcpClient();
                client.NoDelay = true;
                lock (ClientsLock) { Clients.Add(client); }
                Console.WriteLine("[RELAY] WSL bridge connected from {0}", client.Client.RemoteEndPoint);
                Thread reader = new Thread(delegate() { ReadClient(client); });
                reader.IsBackground = true;
                reader.Start();
            }
        }

        private static void ReadClient(TcpClient client)
        {
            try
            {
                using (StreamReader reader = new StreamReader(client.GetStream(), new UTF8Encoding(false)))
                {
                    string line;
                    while ((line = reader.ReadLine()) != null)
                    {
                        byte[] packet = Encoding.UTF8.GetBytes(line);
                        if (CommandFrame.IsMatch(line))
                        {
                            lock (CommandLock)
                            {
                                commandSocket.Send(packet, packet.Length, new IPEndPoint(IPAddress.Loopback, CommandPort));
                            }
                        }
                        else if (StatusFrame.IsMatch(line))
                        {
                            IPEndPoint target;
                            lock (GatewayLock) { target = gatewayAddress; }
                            if (target != null) { stateSocket.Send(packet, packet.Length, target); }
                        }
                    }
                }
            }
            catch (IOException) { }
            catch (SocketException) { }
            finally
            {
                lock (ClientsLock) { Clients.Remove(client); }
                try { client.Close(); } catch { }
                Console.WriteLine("[RELAY] WSL bridge disconnected");
            }
        }

        private static void Broadcast(byte[] packet)
        {
            byte[] frame = new byte[packet.Length + 1];
            Buffer.BlockCopy(packet, 0, frame, 0, packet.Length);
            frame[frame.Length - 1] = (byte)'\n';

            TcpClient[] snapshot;
            lock (ClientsLock) { snapshot = Clients.ToArray(); }
            foreach (TcpClient client in snapshot)
            {
                try
                {
                    NetworkStream stream = client.GetStream();
                    stream.Write(frame, 0, frame.Length);
                }
                catch (IOException)
                {
                    lock (ClientsLock) { Clients.Remove(client); }
                    try { client.Close(); } catch { }
                }
                catch (ObjectDisposedException)
                {
                    lock (ClientsLock) { Clients.Remove(client); }
                }
            }
        }
    }
}
'@

Add-Type -TypeDefinition $source -Language CSharp
[WebotsFiveVFive.Relay]::Run()
