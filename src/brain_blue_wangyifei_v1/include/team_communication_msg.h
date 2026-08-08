#pragma once

#include "types.h"

#define VALIDATION_COMMUNICATION 31202
#define VALIDATION_DISCOVERY 41203
struct TeamCommunicationMsg
{
    int validation = VALIDATION_COMMUNICATION; // validate msg, to determine if it's sent by us.
    int communicationId;
    int teamId;
    int playerId;
    int playerRole; // 1 legacy striker, 2 legacy goal_keeper, 3 legacy defender, 5+ explicit v2 roles
    int assignedRole; // 5 goalkeeper, 6 defender, 7 midfielder, 8 primary_striker, 9 secondary_striker
    bool isAlive; // Whether on the field and not currently penalized
    bool isLead; // Whether in ball-control state
    int leadId; // Deterministic current ball-control owner, 0 means none
    int availability; // 1 active, 2 temporarily missing, 3 unavailable
    bool isInVisualKick; // Whether robot is currently running VisualKick
    bool ballDetected;
    bool ballLocationKnown;
    double ballConfidence;
    double ballRange;
    double cost; // Estimated cost to reach/kick the ball from current state
    Point ballPosToField;
    Pose2D robotPoseToField;
    double kickDir;
    double thetaRb;
    int cmdId; // Each player increments cmdId when publishing; used to indicate message order.
    int cmd; // Encoded command: hundreds digit=1 means self requests ball control; tens digit=1 means goalkeeper requests substitution, units digit stores substitute playerId. e.g. 100 = self requests ball control; 011 = goalkeeper goes out and requests player 1 to substitute.
};

struct TeamDiscoveryMsg
{
    int validation = VALIDATION_DISCOVERY; // validate msg, to determine if it's sent by us.
    int communicationId;
    int teamId;
    int playerId;
};
