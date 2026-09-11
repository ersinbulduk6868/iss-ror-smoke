BeamClass@ g_player = null;
BeamClass@ g_ai_actor = null;
VehicleAIClass@ g_ai = null;
bool g_spawn_attempted = false;
bool g_pair_ready = false;
bool g_stage_active = false;
bool g_blocker_ready = false;
bool g_base1_done = false;
bool g_base2_done = false;
bool g_stage1_done = false;
bool g_stage2_done = false;
bool g_impact_dump_done = false;
bool g_post_dump_done = false;
bool g_need_impact_dump = false;
bool g_stage_fail_logged = false;
float g_pair_timer = 0.0f;
float g_stage_timer = 0.0f;
float g_post_timer = 0.0f;
float g_emit_accum = 0.0f;
int g_stage_stable_frames = 0;
int g_seq = 0;
int g_beam_breaks = 0;
int g_contact_breaks = 0;
int g_resets = 0;
int g_teleports = 0;
vector3 g_player_start(0,0,0);
vector3 g_ai_spawn(0,0,0);

void logNodes(const string &in label, const string &in actorName, BeamClass@ actor)
{
    if (actor == null) return;
    int n = actor.getNodeCount();
    game.log("ISS_NODE_SNAPSHOT_BEGIN label=" + label + " actor=" + actorName + " count=" + n);
    for (int i = 0; i < n; i++)
    {
        vector3 p = actor.getNodePosition(i);
        game.log("ISS_NODE label=" + label + " actor=" + actorName + " idx=" + i + " x=" + p.x + " y=" + p.y + " z=" + p.z);
    }
    game.log("ISS_NODE_SNAPSHOT_END label=" + label + " actor=" + actorName);
}

float horizontalDistance(const vector3 &in a, const vector3 &in b)
{
    float dx = a.x-b.x; float dz = a.z-b.z;
    return sqrt(dx*dx + dz*dz);
}

float minNodeDistance(BeamClass@ a, BeamClass@ b)
{
    if (a == null || b == null) return 9999.0f;
    float best = 9999.0f;
    for (int i=0; i<a.getNodeCount(); i++)
    {
        vector3 pa=a.getNodePosition(i);
        for (int j=0; j<b.getNodeCount(); j++)
        {
            vector3 pb=b.getNodePosition(j);
            float dx=pa.x-pb.x; float dy=pa.y-pb.y; float dz=pa.z-pb.z;
            float d=sqrt(dx*dx+dy*dy+dz*dz);
            if (d<best) best=d;
        }
    }
    return best;
}

float minLaneNodeOffset(BeamClass@ actor, float laneZ)
{
    if (actor == null) return 9999.0f;
    float best=9999.0f;
    for (int i=0; i<actor.getNodeCount(); i++)
    {
        vector3 p=actor.getNodePosition(i);
        float d=abs(p.z-laneZ);
        if (d<best) best=d;
    }
    return best;
}

void main()
{
    game.registerForEvent(SE_TRUCK_BEAM_BROKE);
    game.registerForEvent(SE_TRUCK_RESET);
    game.registerForEvent(SE_TRUCK_TELEPORT);
    game.registerForEvent(SE_GENERIC_NEW_TRUCK);
    game.setTrucksForcedActive(true);
    game.log("ISS_BATTLE_V81_SCRIPT_MAIN");
}

void eventCallback(int eventnum, int value)
{
    if (eventnum == SE_TRUCK_BEAM_BROKE)
    {
        g_beam_breaks++;
        float contactDist=minNodeDistance(g_player,g_ai_actor);
        int accel=0; if (inputs.getEventBoolValue(EV_TRUCK_ACCELERATE)) accel=1;
        int qualified=0;
        if (g_blocker_ready && accel==1 && contactDist<=5.0f)
        {
            g_contact_breaks++;
            qualified=1;
            g_need_impact_dump=true;
            game.log("ISS_BATTLE_CONTACT_DAMAGE_PASS actor="+value+" contactBreaks="+g_contact_breaks+" minNodeDist="+contactDist);
        }
        int blockerFlag=0; if (g_blocker_ready) blockerFlag=1;
        game.log("ISS_BATTLE_BEAM_BROKE actor="+value+" count="+g_beam_breaks+" contactDist="+contactDist+" accel="+accel+" blocker="+blockerFlag+" qualified="+qualified);
    }
    else if (eventnum == SE_TRUCK_RESET)
    {
        g_resets++;
        game.log("ISS_BATTLE_FORBIDDEN_RESET actor="+value+" count="+g_resets);
    }
    else if (eventnum == SE_TRUCK_TELEPORT)
    {
        g_teleports++;
        game.log("ISS_BATTLE_FORBIDDEN_TELEPORT actor="+value+" count="+g_teleports);
    }
    else if (eventnum == SE_GENERIC_NEW_TRUCK)
    {
        game.log("ISS_BATTLE_NEW_TRUCK actor="+value+" total="+game.getNumTrucks());
    }
}

void frameStep(float dt)
{
    if (g_player == null) @g_player=game.getCurrentTruck();
    if (g_player == null) return;

    if (!g_spawn_attempted && game.getNumTrucks()==1)
    {
        g_spawn_attempted=true;
        g_player_start=g_player.getVehiclePosition();
        vector3 spawn=vector3(g_player_start.x-45.0f,g_player_start.y,g_player_start.z-12.0f);
        vector3 orient_ref=vector3(g_player_start.x-45.0f,g_player_start.y,g_player_start.z-24.0f);
        vector3 block_point=vector3(g_player_start.x-45.0f,g_player_start.y,g_player_start.z);
        g_ai_spawn=spawn;
        game.addWaypoint(spawn);
        game.addWaypoint(orient_ref);
        string truck=g_player.getTruckFileName(); string empty="";
        @g_ai_actor=game.spawnTruckAI(truck,spawn,empty,empty,0);
        if (g_ai_actor==null) { game.log("ISS_BATTLE_SPAWN_FAIL"); return; }
        @g_ai=g_ai_actor.getVehicleAI();
        if (g_ai==null) { game.log("ISS_BATTLE_AI_BIND_FAIL"); return; }
        g_ai.addWaypoint("way0",spawn);
        g_ai.addWaypoint("way1",block_point);
        g_ai.setValueAtWaypoint("way0",AI_SPEED,20.0f);
        g_ai.setActive(false);
        game.log("ISS_BATTLE_SECOND_ACTOR_SPAWNED total="+game.getNumTrucks()+" file="+truck+" target_x="+block_point.x+" target_z="+block_point.z);
    }
    if (g_ai_actor==null || g_ai==null || game.getNumTrucks()<2) return;

    g_pair_timer += dt;
    if (!g_base1_done && g_pair_timer>=0.40f)
    {
        logNodes("BASE1","A",g_player); logNodes("BASE1","B",g_ai_actor); g_base1_done=true;
    }
    if (!g_base2_done && g_pair_timer>=1.20f)
    {
        logNodes("BASE2","A",g_player); logNodes("BASE2","B",g_ai_actor); g_base2_done=true; g_pair_ready=true;
        game.log("ISS_BATTLE_PAIR_READY actors="+game.getNumTrucks());
    }

    // Stage B first. A must remain at real accel=0 until blocker-ready.
    if (g_pair_ready && !g_stage_active && !g_blocker_ready)
    {
        if (inputs.getEventBoolValue(EV_TRUCK_ACCELERATE))
        {
            game.log("ISS_BATTLE_STAGE_FAIL_PLAYER_ACCEL_EARLY");
            return;
        }
        g_ai.setActive(true);
        g_stage_active=true;
        g_stage_timer=0.0f;
        game.log("ISS_BATTLE_STAGE_ACTIVE player_accel=0");
    }

    if (g_stage_active && !g_blocker_ready)
    {
        g_stage_timer += dt;
        vector3 pb=g_ai_actor.getVehiclePosition();
        float moved=horizontalDistance(pb,g_ai_spawn);
        float laneOffset=minLaneNodeOffset(g_ai_actor,g_player_start.z);
        float bspeed=g_ai_actor.getSpeed();
        bool downrange=(pb.x<=g_player_start.x-20.0f && pb.x>=g_player_start.x-70.0f);
        bool geometry=(moved>=2.0f && laneOffset<=2.0f && downrange);
        if (geometry && bspeed<0.5f)
        {
            g_stage_stable_frames++;
            if (!g_stage1_done)
            {
                logNodes("STAGE1","A",g_player); logNodes("STAGE1","B",g_ai_actor); g_stage1_done=true;
                game.log("ISS_BATTLE_STAGE1 moved="+moved+" laneOffset="+laneOffset+" bx="+pb.x+" bz="+pb.z+" speed="+bspeed);
            }
        }
        else
        {
            g_stage_stable_frames=0;
        }
        if (geometry && g_stage_stable_frames>=5)
        {
            logNodes("STAGE2","A",g_player); logNodes("STAGE2","B",g_ai_actor); g_stage2_done=true;
            g_blocker_ready=true;
            game.log("ISS_BATTLE_BLOCKER_READY moved="+moved+" laneOffset="+laneOffset+" bx="+pb.x+" bz="+pb.z+" speed="+bspeed+" stableFrames="+g_stage_stable_frames);
        }
        if (g_stage_timer>45.0f && !g_blocker_ready && !g_stage_fail_logged)
        {
            g_stage_fail_logged=true;
            game.log("ISS_BATTLE_BLOCKER_GEOMETRY_FAIL moved="+moved+" laneOffset="+laneOffset+" bx="+pb.x+" bz="+pb.z+" speed="+bspeed+" stableFrames="+g_stage_stable_frames);
        }
    }

    if (g_blocker_ready && inputs.getEventBoolValue(EV_TRUCK_ACCELERATE))
    {
        // This is only a marker; the actual A actuation remains external real XTEST UP.
        if (g_seq % 20 == 0) game.log("ISS_BATTLE_PLAYER_DRIVE_ACTIVE accel_ack=1");
    }

    if (g_need_impact_dump && !g_impact_dump_done)
    {
        logNodes("IMPACT","A",g_player); logNodes("IMPACT","B",g_ai_actor);
        g_impact_dump_done=true; g_need_impact_dump=false; g_post_timer=0.0f;
        game.log("ISS_BATTLE_IMPACT_SNAPSHOT_COMPLETE");
    }
    if (g_impact_dump_done && !g_post_dump_done)
    {
        g_post_timer += dt;
        if (g_post_timer>=3.0f)
        {
            logNodes("POST","A",g_player); logNodes("POST","B",g_ai_actor); g_post_dump_done=true;
            game.log("ISS_BATTLE_POST_SNAPSHOT_COMPLETE");
        }
    }

    vector3 pa=g_player.getVehiclePosition(); vector3 pb=g_ai_actor.getVehiclePosition();
    vector3 mid=vector3((pa.x+pb.x)*0.5f,(pa.y+pb.y)*0.5f,(pa.z+pb.z)*0.5f);
    game.setCameraPosition(vector3(mid.x,mid.y+18.0f,mid.z+28.0f)); game.cameraLookAt(mid);

    g_emit_accum += dt;
    if (g_emit_accum>=0.10f)
    {
        g_emit_accum=0.0f;
        int accel=0; if (inputs.getEventBoolValue(EV_TRUCK_ACCELERATE)) accel=1;
        int stage=0; if (g_stage_active) stage=1;
        int blocker=0; if (g_blocker_ready) blocker=1;
        float dx=pa.x-pb.x; float dz=pa.z-pb.z; float centerDist=sqrt(dx*dx+dz*dz);
        float stageMoved=horizontalDistance(pb,g_ai_spawn); float laneOffset=minLaneNodeOffset(g_ai_actor,g_player_start.z);
        game.log("ISS_BATTLE_TELEM_V81 seq="+g_seq
          +" ax="+pa.x+" ay="+pa.y+" az="+pa.z+" aspeed="+g_player.getSpeed()
          +" bx="+pb.x+" by="+pb.y+" bz="+pb.z+" bspeed="+g_ai_actor.getSpeed()
          +" centerDist="+centerDist+" stageMoved="+stageMoved+" laneOffset="+laneOffset
          +" accel="+accel+" stage="+stage+" blocker="+blocker
          +" breaks="+g_beam_breaks+" contactBreaks="+g_contact_breaks
          +" resets="+g_resets+" teleports="+g_teleports+" actors="+game.getNumTrucks());
        g_seq++;
    }
}
