#include "brain.h"
#include "brain_communication.h"

static_assert(sizeof(TeamCommunicationMsg) <= 512, "TeamCommunicationMsg must be <= 512 bytes");

namespace {
int roleNameToWireCode(const std::string &role) {
    if (role == "striker") return 1;
    if (role == "goal_keeper" || role == "goalkeeper") return 5;
    if (role == "defender") return 6;
    if (role == "midfielder") return 7;
    if (role == "primary_striker") return 8;
    if (role == "secondary_striker") return 9;
    return 4;
}

std::string wireCodeToRoleName(int role) {
    switch (role) {
    case 1: return "primary_striker";
    case 2: return "goalkeeper";
    case 3: return "defender";
    case 5: return "goalkeeper";
    case 6: return "defender";
    case 7: return "midfielder";
    case 8: return "primary_striker";
    case 9: return "secondary_striker";
    default: return "unknown";
    }
}
}

BrainCommunication::BrainCommunication(Brain *argBrain) : brain(argBrain)
{
}

BrainCommunication::~BrainCommunication()
{
    clearupGameControllerUnicast();
    clearupTeamBroadcast();
    clearupTeamReceiver();
}


void BrainCommunication::initCommunication()
{
    initGameControllerUnicast();
    if (brain->config->get_enable_com())
    {
        cout << RED_CODE << "Communication enabled." << RESET_CODE << endl;
        _team_udp_port = 10000 + brain->config->get_team_id(); // Rule: 10000 + teamId

        initTeamBroadcast();
        initTeamReceiver();
    }
    else
    {
        cout << RED_CODE << "Communication disabled." << RESET_CODE << endl;
    }
}
    

void BrainCommunication::initGameControllerUnicast()
{
    try
    {
        _gc_send_socket = socket(AF_INET, SOCK_DGRAM, 0);
        if (_gc_send_socket < 0)
        {
        cout << RED_CODE << format("gc socket failed: %s", strerror(errno))
            << RESET_CODE << endl;
        throw std::runtime_error(strerror(errno));
        }
        // 配置目标地址
        string gamecontrol_ip = brain->get_parameter("game_control_ip").as_string();
        cout << GREEN_CODE << format("GameControl IP: %s", gamecontrol_ip.c_str())
            << RESET_CODE << endl;
        _gcsaddr.sin_family = AF_INET;
        _gcsaddr.sin_addr.s_addr = inet_addr(gamecontrol_ip.c_str());
        _gcsaddr.sin_port = htons(GAMECONTROLLER_RETURN_PORT);

        _unicast_gamecontrol_flag = true;
        _gamecontrol_unicast_thread = std::thread([this](){ this->unicastToGameController(); });
    }
    catch(const std::exception& e)
    {
        std::cerr << e.what() << '\n';
    }
}

void BrainCommunication::clearupGameControllerUnicast()
{
    _unicast_gamecontrol_flag = false;
    if (_gc_send_socket >= 0)
    {
        close(_gc_send_socket);
        _gc_send_socket = -1;
        cout << RED_CODE << format("GameControl send socket has been closed.")
            << RESET_CODE << endl;
    }
    if (_gamecontrol_unicast_thread.joinable())
    {
        _gamecontrol_unicast_thread.join();
    }
}


void BrainCommunication::unicastToGameController() {
    while (_unicast_gamecontrol_flag)
    {
        // cout << RED_CODE << format("unicastToGameController header=%s version=%d teamId=%d, playerId=%d", gc_return_data.header, gc_return_data.version, brain->config->get_team_id(), brain->config->get_player_id())
        //     << RESET_CODE << endl;
        gc_return_data.teamNum = brain->config->get_team_id();
        gc_return_data.playerNum = brain->config->get_player_id();
        // Fallback values: robot can play, no localization feedback to GC.
        gc_return_data.fallen = 0;

        int ret = sendto(_gc_send_socket, &gc_return_data, sizeof(gc_return_data), 0, (sockaddr *)&_gcsaddr, sizeof(_gcsaddr));
        if (ret < 0)
        {
            cout << RED_CODE << format("gc sendto failed: %s", strerror(errno))
                << RESET_CODE << endl;
        }
        this_thread::sleep_for(chrono::milliseconds(BROADCAST_GAME_CONTROL_INTERVAL_MS)); // 500ms = 2 packets per second
    }
}

void BrainCommunication::initTeamBroadcast()
{
    try
    {
        _team_send_socket = socket(AF_INET, SOCK_DGRAM, 0);
        if (_team_send_socket < 0)
        {
            cout << RED_CODE << format("socket failed: %s", strerror(errno))
                << RESET_CODE << endl;
            throw std::runtime_error(strerror(errno));
        }

        // 设置广播选项
        int broadcast = 1;
        if (setsockopt(_team_send_socket, SOL_SOCKET, SO_BROADCAST, 
                    &broadcast, sizeof(broadcast)) < 0)
        {
            cout << RED_CODE << format("Failed to set SO_BROADCAST: %s", strerror(errno))
                << RESET_CODE << endl;
            throw std::runtime_error(strerror(errno));
        }

        // 配置广播地址
        _team_saddr.sin_family = AF_INET;
        _team_saddr.sin_addr.s_addr = INADDR_BROADCAST;  // 255.255.255.255
        _team_saddr.sin_port = htons(_team_udp_port);

        // 由配置计算队内广播间隔（默认 2Hz = 500ms?
        double hz = brain->config->get_team_comm_frequency_hz();
        if (hz <= 0.0) {
            cout << RED_CODE << format("team_comm_frequency_hz=%.2f <= 0, fallback to 2.0Hz", hz)
                << RESET_CODE << endl;
            hz = 2.0;
        }
        if (hz > 2.0) {
            cout << RED_CODE << format("team_comm_frequency_hz=%.2f exceeds RoboCup 2 packets/sec rule! (still applied)", hz)
                << RESET_CODE << endl;
        }
        _team_broadcast_interval_ms = static_cast<int>(1000.0 / hz + 0.5);
        cout << GREEN_CODE << format("Team broadcast frequency: %.2f Hz (interval %d ms)", hz, _team_broadcast_interval_ms)
            << RESET_CODE << endl;

        _broadcast_team_flag = true;
        _team_broadcast_thread = std::thread([this](){ this->broadcastTeamCommunication(); });
        
        cout << GREEN_CODE << format("Team broadcast initialized on port %d", _team_udp_port)
            << RESET_CODE << endl;
    }
    catch(const std::exception& e)
    {
        std::cerr << e.what() << '\n';
        brain->log->log("error/communication", format("Failed to initialize team broadcast: %s", e.what()));
    }
}

void BrainCommunication::clearupTeamBroadcast()
{
    _broadcast_team_flag = false;
    if (_team_send_socket >= 0)
    {
        close(_team_send_socket);
        _team_send_socket = -1;
        cout << RED_CODE << format("Team broadcast socket has been closed.")
            << RESET_CODE << endl;
    }

    if (_team_broadcast_thread.joinable())
    {
        _team_broadcast_thread.join();
    }
}

void BrainCommunication::broadcastTeamCommunication() {

    while (_broadcast_team_flag)
    {
        TeamCommunicationMsg msg;
        msg.validation = VALIDATION_COMMUNICATION;
        msg.communicationId = _team_communication_msg_id++;
        msg.teamId = brain->config->get_team_id();
        msg.playerId = brain->config->get_player_id();
        string role = brain->tree->getEntry<string>("player_role");
        msg.playerRole = roleNameToWireCode(role);
        msg.assignedRole = roleNameToWireCode(brain->data->assignedRole);
        msg.isAlive = brain->data->tmImAlive;
        msg.isLead = brain->data->tmImLead;
        msg.leadId = brain->data->currentLeadId;
        msg.availability = brain->data->selfAvailability;
        msg.isInVisualKick = brain->data->tmImInVisualKick;
        msg.ballDetected = brain->data->ballDetected;
        msg.ballLocationKnown = brain->tree->getEntry<bool>("ball_location_known");
        msg.ballConfidence = brain->data->ball.confidence;
        msg.ballRange = brain->data->ball.range;
        msg.cost = brain->data->tmMyCost;
        msg.ballPosToField = brain->data->ball.posToField;
        msg.robotPoseToField = brain->data->robotPoseToField;
        msg.kickDir = brain->data->kickDir;
        msg.thetaRb = brain->data->robotBallAngleToField;
        msg.cmdId = brain->data->tmMyCmdId;
        msg.cmd = brain->data->tmMyCmd;

        if (brain->isRecoveryActive()) {
            msg.isAlive = false;
            msg.isLead = false;
            msg.isInVisualKick = false;
            msg.ballDetected = false;
            msg.ballLocationKnown = false;
            msg.ballConfidence = 0.0;
            msg.ballRange = 1e6;
            msg.cost = 1e6;
            msg.cmd = 0;
        }

        // 验证消息大小不超?12字节（规则要求）
        size_t msgSize = sizeof(TeamCommunicationMsg);
        if (msgSize > 512) {
            cout << RED_CODE << format("TeamCommunicationMsg size (%zu bytes) exceeds 512 bytes limit!", msgSize)
                << RESET_CODE << endl;
            brain->log->log("error/communication", format("Message size violation: %zu bytes", msgSize));
        }

        brain->data->sendId = msg.communicationId;
        brain->data->sendTime = brain->get_clock()->now();

        // 检查游戏状态：仅在 READY/SET/PLAY 状态计数（规则要求?
        string gameState = brain->tree->getEntry<string>("gc_game_state");
        bool shouldCount = (gameState == "READY" || gameState == "SET" || gameState == "PLAY");
        
        int ret = sendto(_team_send_socket, &msg, sizeof(msg), 0, (sockaddr *)&_team_saddr, sizeof(_team_saddr));
        if (ret < 0) {
            cout << RED_CODE << format("broadcast sendto failed: %s", strerror(errno))
                << RESET_CODE << endl;
        } else if (shouldCount) {
            // 仅在允许的状态下计数
            _counted_messages++;

            // ?0条消息打印一次到控制台，避免日志过多
            if (_counted_messages % 50 == 0) {
                cout << GREEN_CODE << format("Communication: Sent %d counted messages (READY/SET/PLAY states only, current state: %s)", _counted_messages, gameState.c_str())
                    << RESET_CODE << endl;
            }
        }
        
        this_thread::sleep_for(chrono::milliseconds(_team_broadcast_interval_ms)); // ?team_comm_frequency_hz 配置, 默认 500ms = 2 ??
    }
}

void BrainCommunication::initTeamReceiver() {
    try
    {
        _team_recv_socket = socket(AF_INET, SOCK_DGRAM, 0);
        if (_team_recv_socket < 0) {
            cout << RED_CODE << format("socket failed: %s", strerror(errno))
                << RESET_CODE << endl;
            throw std::runtime_error(strerror(errno));
        }

        // 允许地址重用
        int reuse = 1;
        if (setsockopt(_team_recv_socket, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse)) < 0)
        {
            cout << RED_CODE << format("Failed to set SO_REUSEADDR: %s", strerror(errno))
                << RESET_CODE << endl;
            throw std::runtime_error(strerror(errno));
        }

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_ANY);  // 接收所有网络接口的数据
        addr.sin_port = htons(_team_udp_port);
        
        if (bind(_team_recv_socket, (sockaddr *)&addr, sizeof(addr)) < 0) {
            cout << RED_CODE << format("bind failed: %s (port=%d)", strerror(errno), _team_udp_port)
                << RESET_CODE << endl;
            throw std::runtime_error(strerror(errno));
        }

        cout << GREEN_CODE << format("Listening for team UDP broadcast on port %d", _team_udp_port)
            << RESET_CODE << endl;

        _receive_team_flag = true;
        _team_recv_thread = std::thread([this](){ this->spinTeamReceiver(); });
    }
    catch(const std::exception& e)
    {
        std::cerr << e.what() << '\n';
        brain->log->log("error/communication", format("Failed to initialize team receiver: %s", e.what()));
    }
}

void BrainCommunication::clearupTeamReceiver() {
    _receive_team_flag = false;
    if (_team_recv_socket >= 0) {
        close(_team_recv_socket);
        _team_recv_socket = -1;
        cout << RED_CODE << format("Team receive socket has been closed.")
            << RESET_CODE << endl;
    }
    if (_team_recv_thread.joinable()) {
        _team_recv_thread.join();
    }
}

void BrainCommunication::spinTeamReceiver() {

    sockaddr_in addr{};
    socklen_t addr_len = sizeof(addr);

    TeamCommunicationMsg msg;

    while (_receive_team_flag) {

        ssize_t len = recvfrom(_team_recv_socket, &msg, sizeof(msg), 0, (sockaddr *)&addr, &addr_len);

        if (len < 0) {
            cout << RED_CODE << format("receiving UDP message failed: %s", strerror(errno))
                << RESET_CODE << endl;
            continue;
        }

        if (len != sizeof(TeamCommunicationMsg)) {
            cout << YELLOW_CODE << format("received TeamCommunicationMsg packet with wrong size: %ld, expected: %ld", len, sizeof(TeamCommunicationMsg))
                << RESET_CODE << endl;
            continue;
        }

        if (msg.validation != VALIDATION_COMMUNICATION) { // fail to pass validation
            cout << RED_CODE << format("received TeamCommunicationMsg packet with invalid validation: %d", msg.validation)
                << RESET_CODE << endl;
            continue;
        }

        if (msg.teamId != brain->config->get_team_id()) { // 忽略其它队伍的消?
            cout << YELLOW_CODE << format("Received message from team %d, expected team %d", msg.teamId, brain->config->get_team_id())
                << RESET_CODE << endl;
            continue;
        }

        if (msg.playerId == brain->config->get_player_id()) {  // 忽略自己的消?
            // 处理自己的消息（用于调试?
            brain->data->sendId = msg.communicationId;
            brain->data->sendTime = brain->get_clock()->now();
            continue;
        } 

        // 处理队友消息
        auto tmIdx = msg.playerId - 1;

        if (tmIdx < 0 || tmIdx >= HL_MAX_NUM_PLAYERS) { // HL_MAX_NUM_PLAYERS 是最大球员数
            cout << YELLOW_CODE << format("Received message with invalid playerId: %d", msg.playerId) << RESET_CODE << endl;
            continue;
        }

        if (brain->data->penalty[tmIdx] == SUBSTITUTE) { // 不处理替补队员的信息
            cout << YELLOW_CODE << format("Communication playerId %d is substitute", msg.playerId) << RESET_CODE << endl;
            continue;
        }


        TMStatus &tmStatus = brain->data->tmStatus[tmIdx];
        
        const int roleCode = msg.assignedRole != 0 ? msg.assignedRole : msg.playerRole;
        tmStatus.role = wireCodeToRoleName(roleCode);
        tmStatus.assignedRoleCode = roleCode;
        tmStatus.leadId = msg.leadId;
        tmStatus.availability = msg.availability;
        tmStatus.isAlive = msg.isAlive;
        tmStatus.ballDetected = msg.ballDetected;
        tmStatus.ballLocationKnown = msg.ballLocationKnown;
        tmStatus.ballConfidence = msg.ballConfidence;
        tmStatus.ballRange = msg.ballRange;
        tmStatus.cost = msg.cost;
        tmStatus.isLead = msg.isLead;
        tmStatus.isInVisualKick = msg.isInVisualKick;
        tmStatus.ballPosToField = msg.ballPosToField;
        tmStatus.robotPoseToField = msg.robotPoseToField;
        tmStatus.kickDir = msg.kickDir;
        tmStatus.thetaRb = msg.thetaRb;
        tmStatus.timeLastCom = brain->get_clock()->now();
        tmStatus.cmd = msg.cmd;
        tmStatus.cmdId = msg.cmdId;

        // 检查是否收到了新的指令
        if (msg.cmdId > brain->data->tmCmdId) {
            brain->data->tmCmdId = msg.cmdId;
            brain->data->tmReceivedCmd = msg.cmd;
            brain->data->tmLastCmdChangeTime = brain->get_clock()->now();
        }
    }
}
