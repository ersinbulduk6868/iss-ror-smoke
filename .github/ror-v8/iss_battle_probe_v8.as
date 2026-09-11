BeamClass@ g_player = null;
BeamClass@ g_ai_actor = null;
VehicleAIClass@ g_ai = null;
bool g_spawn_attempted = false;
bool g_pair_ready = false;
bool g_ai_active = false;
bool g_base1_done = false;
bool g_base2_done = false;
bool g_impact_dump_done = false;
bool g_post_dump_done = false;
bool g_need_impact_dump = false;
float g_pair_timer = 0.0f;
float g_post_timer = 0.0f;
float g_emit_accum = 0.0f;
int g_seq = 0;
int g_beam_breaks = 0;
int g_contact_breaks = 0;
int g_resets = 0;
int g_teleports = 0;

void logNodes(const string &in label, const string &in actorName, BeamClass@ actor)
{
    if (actor == null)
        return;
    int n = actor.getNodeCount();
    game.log("ISS_NODE_SNAPSHOT_BEGIN label=" + label + " actor=" + actorName + " count=" + n);
    for (int i = 0; i < n; i++)
    {
        vector3 p = actor.getNodePosition(i);
        game.log("ISS_NODE label=" + label + " actor=" + actorName + " idx=" + i + " x=" + p.x + " y=" + p.y + " z=" + p.z);
    }
    game.log("ISS_NODE_SNAPSHOT_END label=" + label + " actor=" + actorName);
}

float minNodeDistance(BeamClass@ a, BeamClass@ b)
{
    if (a == null || b == null)
        return 9999.0f;
    float best = 9999.0f;
    int na = a.getNodeCount();
    int nb = b.getNodeCount();
    for (int i = 0; i < na; i++)
    {
        vector3 pa = a.getNodePosition(i);
        for (int j = 0; j < nb; j++)
        {
            vector3 pb = b.getNodePosition(j);
            float dx = pa.x - pb.x;
            float dy = pa.y - pb.y;
            float dz = pa.z - pb.z;
            float d = sqrt(dx * dx + dy * dy + dz * dz);
            if (d < best)
                best = d;
        }
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
    game.log("ISS_BATTLE_V8_SCRIPT_MAIN");
}

void eventCallback(int eventnum, int value)
{
    if (eventnum == SE_TRUCK_BEAM_BROKE)
    {
        g_beam_breaks++;
        float contactDist = minNodeDistance(g_player, g_ai_actor);
        int accel = 0;
        if (inputs.getEventBoolValue(EV_TRUCK_ACCELERATE))
            accel = 1;
        int aiActive = 0;
        if (g_ai_active)
            aiActive = 1;
        int qualified = 0;
        if (g_ai_active && accel == 1 && contactDist <= 5.0f)
        {
            g_contact_breaks++;
            qualified = 1;
            g_need_impact_dump = true;
            game.log("ISS_BATTLE_CONTACT_DAMAGE_PASS actor=" + value
                + " contactBreaks=" + g_contact_breaks + " minNodeDist=" + contactDist);
        }
        game.log("ISS_BATTLE_BEAM_BROKE actor=" + value + " count=" + g_beam_breaks
            + " contactDist=" + contactDist + " accel=" + accel
            + " ai=" + aiActive + " qualified=" + qualified);
    }
    else if (eventnum == SE_TRUCK_RESET)
    {
        g_resets++;
        game.log("ISS_BATTLE_FORBIDDEN_RESET actor=" + value + " count=" + g_resets);
    }
    else if (eventnum == SE_TRUCK_TELEPORT)
    {
        g_teleports++;
        game.log("ISS_BATTLE_FORBIDDEN_TELEPORT actor=" + value + " count=" + g_teleports);
    }
    else if (eventnum == SE_GENERIC_NEW_TRUCK)
    {
        game.log("ISS_BATTLE_NEW_TRUCK actor=" + value + " total=" + game.getNumTrucks());
    }
}

void frameStep(float dt)
{
    if (g_player == null)
        @g_player = game.getCurrentTruck();
    if (g_player == null)
        return;

    if (!g_spawn_attempted && game.getNumTrucks() == 1)
    {
        g_spawn_attempted = true;
        vector3 p = g_player.getVehiclePosition();
        // V7 proves the stock semi moves toward decreasing X under real UP input.
        // Put actor B 45 m down that lane but 12 m laterally offset. The two
        // SurveyMap waypoints below are ONLY the spawn-orientation contract used
        // by spawnTruckAI(): pinned RoR computes rotation from wp[0]-wp[1].
        // spawn - orient_ref points +Z, so B starts perpendicular to A's lane.
        vector3 spawn = vector3(p.x - 45.0f, p.y, p.z - 12.0f);
        vector3 orient_ref = vector3(p.x - 45.0f, p.y, p.z - 24.0f);
        vector3 block_point = vector3(p.x - 45.0f, p.y, p.z);
        game.addWaypoint(spawn);
        game.addWaypoint(orient_ref);
        string truck = g_player.getTruckFileName();
        string empty = "";
        @g_ai_actor = game.spawnTruckAI(truck, spawn, empty, empty, 0);
        if (g_ai_actor == null)
        {
            game.log("ISS_BATTLE_SPAWN_FAIL");
            return;
        }
        @g_ai = g_ai_actor.getVehicleAI();
        if (g_ai == null)
        {
            game.log("ISS_BATTLE_AI_BIND_FAIL");
            return;
        }
        // VehicleAI owns a separate waypoint list. B first traverses the 12 m
        // lateral leg into A's proven X lane, then naturally disables/parks on
        // its final waypoint. This avoids relying on newer GUI-mode setter APIs and
        // turns the pinned normal-mode collision avoidance into a safe parked
        // target rather than an unproven head-on-AI assumption.
        g_ai.addWaypoint("way0", spawn);
        g_ai.addWaypoint("way1", block_point);
        g_ai.setValueAtWaypoint("way0", AI_SPEED, 20.0f);
        g_ai.setActive(false);
        game.log("ISS_BATTLE_SECOND_ACTOR_SPAWNED total=" + game.getNumTrucks()
            + " file=" + truck + " target_x=" + block_point.x + " target_z=" + block_point.z);
    }

    if (g_ai_actor == null || g_ai == null || game.getNumTrucks() < 2)
        return;

    g_pair_timer += dt;
    if (!g_base1_done && g_pair_timer >= 0.40f)
    {
        logNodes("BASE1", "A", g_player);
        logNodes("BASE1", "B", g_ai_actor);
        g_base1_done = true;
    }
    if (!g_base2_done && g_pair_timer >= 1.20f)
    {
        logNodes("BASE2", "A", g_player);
        logNodes("BASE2", "B", g_ai_actor);
        g_base2_done = true;
        g_pair_ready = true;
        game.log("ISS_BATTLE_PAIR_READY actors=" + game.getNumTrucks());
    }

    if (g_pair_ready && !g_ai_active && inputs.getEventBoolValue(EV_TRUCK_ACCELERATE))
    {
        g_ai.setActive(true);
        g_ai_active = true;
        game.log("ISS_BATTLE_AI_ACTIVE accel_ack=1");
    }

    if (g_need_impact_dump && !g_impact_dump_done)
    {
        logNodes("IMPACT", "A", g_player);
        logNodes("IMPACT", "B", g_ai_actor);
        g_impact_dump_done = true;
        g_need_impact_dump = false;
        g_post_timer = 0.0f;
        game.log("ISS_BATTLE_IMPACT_SNAPSHOT_COMPLETE");
    }

    if (g_impact_dump_done && !g_post_dump_done)
    {
        g_post_timer += dt;
        if (g_post_timer >= 3.0f)
        {
            logNodes("POST", "A", g_player);
            logNodes("POST", "B", g_ai_actor);
            g_post_dump_done = true;
            game.log("ISS_BATTLE_POST_SNAPSHOT_COMPLETE");
        }
    }

    vector3 pa = g_player.getVehiclePosition();
    vector3 pb = g_ai_actor.getVehiclePosition();
    vector3 mid = vector3((pa.x + pb.x) * 0.5f, (pa.y + pb.y) * 0.5f, (pa.z + pb.z) * 0.5f);
    game.setCameraPosition(vector3(mid.x, mid.y + 18.0f, mid.z + 28.0f));
    game.cameraLookAt(mid);

    g_emit_accum += dt;
    if (g_emit_accum >= 0.10f)
    {
        g_emit_accum = 0.0f;
        float dx = pa.x - pb.x;
        float dz = pa.z - pb.z;
        float centerDist = sqrt(dx * dx + dz * dz);
        int accel = 0;
        if (inputs.getEventBoolValue(EV_TRUCK_ACCELERATE))
            accel = 1;
        int aiFlag = 0;
        if (g_ai_active)
            aiFlag = 1;
        game.log("ISS_BATTLE_TELEM seq=" + g_seq
            + " ax=" + pa.x + " ay=" + pa.y + " az=" + pa.z + " aspeed=" + g_player.getSpeed()
            + " bx=" + pb.x + " by=" + pb.y + " bz=" + pb.z + " bspeed=" + g_ai_actor.getSpeed()
            + " centerDist=" + centerDist + " accel=" + accel
            + " ai=" + aiFlag
            + " breaks=" + g_beam_breaks + " contactBreaks=" + g_contact_breaks
            + " resets=" + g_resets + " teleports=" + g_teleports
            + " actors=" + game.getNumTrucks());
        g_seq++;
    }
}
