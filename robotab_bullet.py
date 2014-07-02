from random import choice, randrange

import uwsgi
import gevent
import gevent.queue
import gevent.event
import gevent.select
import redis
import math
from bulletphysics import *


class StaticBox(object):

    def __init__(self, world, size_x, size_y, size_z, x, y, z, r):
        self.shape = BoxShape(Vector3(size_x*10, size_y, size_z*6))
        q = Quaternion(0, 0, 0, 1)
        q.setRotation(Vector3(0.0, 1.0, 0.0), r)
        self.motion_state = DefaultMotionState(
            Transform(q, Vector3(x, y, z)))
        construction_info = RigidBodyConstructionInfo(
            0, self.motion_state, self.shape, Vector3(0, 0, 0))
        construction_info.m_friction = -1.0
        self.body = RigidBody(construction_info)
        world.addRigidBody(self.body)


class Box(object):

    def __init__(self, game, mass, size_x, size_y, size_z, x, y, z, r, friction=0.5):
        self.game = game
        self.mass = mass
        self.shape = BoxShape(Vector3(size_x, size_y, size_z))
        q = Quaternion(0, 0, 0, 1)
        q.setRotation(Vector3(0.0, 1.0, 0.0), r)
        self.motion_state = DefaultMotionState(
            Transform(q, Vector3(x, y, z)))
        self.inertia = Vector3(0, 0, 0)
        self.shape.calculateLocalInertia(self.mass, self.inertia)
        construction_info = RigidBodyConstructionInfo(
            self.mass, self.motion_state, self.shape, self.inertia)
        construction_info.m_friction = friction
        self.body = RigidBody(construction_info)
        self.game.world.addRigidBody(self.body)
        self.trans = Transform()
        self.origin = self.trans.getOrigin()


class Arena(object):

    def __init__(self, min_players=3, max_players=8, warmup=10):
        self.greenlets = {
            'engine': self.engine_start,
            # 'start': self.start
        }

        self.posters = [
            'posters/robbo.jpg',
            'posters/raffo.jpg',
            'posters/unbit.jpg',
            'posters/20tab.jpg',
            'posters/beri.jpg',
            'posters/pycon.jpg'
        ]

        self.animations = []
        self.players = {}
        self.waiting_players = []
        self.min_players = min_players
        self.max_players = max_players
        self.warmup = warmup
        self.started = False
        self.finished = False
        #self.warming_up = False
        self.walls = []
        self.ground_coordinates = (270, 1, 270, 0, 0, 0, 1)
        self.walls_coordinates = (
            #sc_x,  sc_y,   sc_z,     x,       y,     z,            r
            (200,     100,     50,     0,     150, -1950,            0),
            (200,     100,     50, -1950,     150,     0, -math.pi / 2),
            (200,     100,     50,  1950,     150,     0, -math.pi / 2),
            (200,     100,     50,     0,     150,  1950,            0),

            ( 50,      50,     30,  -730,     150, -1200,            0),
            ( 50,      50,     30,   730,     150, -1200,            0),

            ( 50,      50,     30, -1200,     150,  -730, -math.pi / 2),
            ( 50,      50,     30, -1200,     150,   730, -math.pi / 2),

            ( 50,      50,     30,  1200,     150,  -730, -math.pi / 2),
            ( 50,      50,     30,  1200,     150,   730, -math.pi / 2),

            ( 50,      50,     30,  -730,     150,  1200,            0),
            ( 50,      50,     30,   730,     150,  1200,            0),
        )

        self.spawn_points = (
            #    x,     y,   z,               r,    color
            #(    0,  1650,         math.pi),
            #(    0, -1650,               0),
            ( -935,    35,   935,  3 * math.pi / 4, 0x7777AA),
            (  935,    35,   935,  5 * math.pi / 4, 0x770000),
            (  935,    35,  -935,  7 * math.pi / 4, 0x007700),
            ( -935,    35,  -935,      math.pi / 4, 0x777700),
            (-1650,    35,  1650,  3 * math.pi / 4, 0xAA00AA),
            #(-1650,     0,     math.pi / 2),
            #( 1650,     0, 3 * math.pi / 2),
            ( 1650,    35,  1650,  5 * math.pi / 4, 0x007777),
            ( 1650,    35, -1650,  7 * math.pi / 4, 0x000077),
            (-1650,    35, -1650,      math.pi / 4, 0xFFAA77),

        )

        self.broadphase = DbvtBroadphase()
        self.collisionConfiguration = DefaultCollisionConfiguration()
        self.dispatcher = CollisionDispatcher(self.collisionConfiguration)
        self.solver = SequentialImpulseConstraintSolver()
        self.world = DiscreteDynamicsWorld(
            self.dispatcher, self.broadphase,
            self.solver, self.collisionConfiguration)
        self.world.setGravity(Vector3(0, -9.81, 0))

        # self.ground_shape = StaticPlaneShape(Vector3(0, 1, 0), 1)

        # q = Quaternion(0, 0, 0, 1)
        # self.ground_motion_state = DefaultMotionState(
        #     Transform(q, Vector3(0, -1, 0)))

        # construction_info = RigidBodyConstructionInfo(
        #     0, self.ground_motion_state, self.ground_shape, Vector3(0, 0, 0))
        # construction_info.m_friction = 0.52
        # self.ground = RigidBody(construction_info)

        # self.world.addRigidBody(self.ground)
        self.ground = StaticBox(self.world, *self.ground_coordinates)

        # for wall_c in self.walls_coordinates:
        #     wall = StaticBox(self.world, *wall_c)
        #     self.walls.append(wall)

        self.arena = "arena{}".format(uwsgi.worker_id())
        self.redis = redis.StrictRedis()
        self.channel = self.redis.pubsub()
        self.channel.subscribe(self.arena)

        # self.bonus_malus = (
        #     BonusHaste,
        #     # BonusGiant,
        #     BonusPower,
        #     BonusHeal,
        # )

        self.bonus_malus_spawn_points = [
            (    0,     0),
            (    0,  1650),
            (    0, -1650),
            (-1650,     0),
            ( 1650,     0),
        ]

        self.active_bonus_malus = []

        self.spawn_iterator = iter(self.spawn_points)

    def broadcast(self, msg):
        self.redis.publish(self.arena, 'arena:{}'.format(msg))

    def msg_handler(self, player, msg):
        p, cmd = msg.split(':')
        if cmd not in ('at', 'AT'):
            self.players[p].cmd = cmd

    def cmd_handler(self, player, cmd):
        if cmd == 'rl':
            orientation = player.body.getOrientation()
            v = Vector3(0, 1000, 0).rotate(
                orientation.getAxis(), orientation.getAngle())
            player.body.activate(True)
            player.body.applyTorqueImpulse(v)
            return True

        if cmd == 'rr':
            orientation = player.body.getOrientation()
            v = Vector3(0, -1000, 0).rotate(
                orientation.getAxis(), orientation.getAngle())
            player.body.activate(True)
            player.body.applyTorqueImpulse(v)
            return True

        if cmd == 'fw':
            orientation = player.body.getOrientation()
            v = Vector3(0, 0, 500).rotate(
                orientation.getAxis(), orientation.getAngle())
            player.body.activate(True)
            player.body.applyCentralImpulse(v)
            return True

        if cmd == 'bw':
            orientation = player.body.getOrientation()
            v = Vector3(0, 0, -500).rotate(
                orientation.getAxis(), orientation.getAngle())
            player.body.activate(True)
            player.body.applyCentralImpulse(v)
            return True

        return False

    def engine_start(self):
        del self.greenlets['engine']
        print('engine started')
        while True:
            t = uwsgi.micros() / 1000.0
            if len(self.players) == 1 and self.started:
                self.finished = True
                self.winning_logic()
                self.restart_game(11)
                break
            elif len(self.players) == 0:
                self.finished = True
                self.restart_game()
                break

            self.world.stepSimulation(1, 30)
            for p in self.players.keys():
                player = self.players[p]
                # if player.cmd:
                #     draw = self.cmd_handler(player, player.cmd)
                #     draw = True
                #     if draw:
                #         player.update_gfx()
                #     player.cmd = None
                if player.cmd:
                    self.cmd_handler(player, player.cmd)
                    player.cmd = None
                player.update_gfx()
            t1 = uwsgi.micros() / 1000.0
            delta = t1 - t
            if delta < 33.33:
                gevent.sleep((33.33 - delta) / 1000.0)
        self.greenlets['engine'] = self.engine_start
        print("engine ended")

    def start(self):
        del self.greenlets['start']
        print("START!!")
        #self.warming_up = True

        while len(self.players) < self.min_players:
            # for p in self.players.keys():
            #     self.players[p].update_gfx()
            gevent.sleep(1)
            if self.finished:
                self.greenlets['start'] = self.start
                print("ending")
                return

        warmup = self.warmup

        while warmup > 0:
            gevent.sleep(1.0)
            self.broadcast("warmup,{} seconds to start".format(warmup))
            warmup -= 1
        #self.warmup = False
        self.started = True
        #gevent.spawn(self.engine_start)
        gevent.sleep()
        self.broadcast("FIGHT!!!")
        gevent.sleep()

        bm_counter = 0
        while not self.finished:
            gevent.sleep(10.0)
            # if len(self.bonus_malus_spawn_points) > 0:
            #     coordinates = self.bonus_malus_spawn_points.pop(randrange(len(self.bonus_malus_spawn_points)))
            #     choice(self.bonus_malus)(self, bm_counter, *(coordinates))
            #     bm_counter += 1
        gevent.sleep(1.0)
        self.broadcast("end")
        self.started = False
        self.greenlets['start'] = self.start
        print("end")
        gevent.sleep()

    def spawn_greenlets(self):
        for greenlet in self.greenlets:
            #if len(self.players) >= self.min_players:
            if len(self.players) >= 1:
                gevent.spawn(self.greenlets[greenlet])

    # place up to 8 waiting_players
    # in the player list and start the game again
    # unless less than 2 players are available
    def winning_logic(self):
        winner_name = self.players.keys()[0]
        self.players[winner_name].end('winner')

    def restart_game(self, countdown=15):
        countdown = countdown
        while countdown > 0:
            self.broadcast(
                'next game will start in {} seconds'.format(countdown))
            gevent.sleep(1)
            countdown -= 1
        self.finished = False
        self.players = {}
        if len(self.waiting_players) > 0:
            for player in self.waiting_players:
                self.players[player.name] = player
                if len(self.players) >= self.max_players:
                    break
        self.broadcast('waiting for players')


class Player(Box):

    def __init__(self, game, name, avatar, fd, x, y, z, r, color, scale=5, speed=15):
        self.size_x = 25
        self.size_y = 45
        self.size_z = 35
        super(Player, self).__init__(game, 90.0, self.size_x, self.size_y, self.size_z, x, y, z, r)
        self.name = name
        self.avatar = avatar
        self.fd = fd

        self.last_msg = None

        self.scale = scale

        # self.attack = 0
        self.energy = 100.0
        self.arena = "arena{}".format(uwsgi.worker_id())
        self.redis = redis.StrictRedis()
        self.channel = self.redis.pubsub()
        self.channel.subscribe(self.arena)
        self.redis_fd = self.channel.connection._sock.fileno()

        self.cmd = None
        # self.bullet = Bullet(self.game, self)
        self.color = color

        # check if self.energy is 0, in such a case
        # trigger the kill procedure removing the player from the list
        # if after the death a single player remains,
        # trigger the winning procedure
    def damage(self, amount, attacker):
        if not self.game.started:
            return
        self.energy -= amount
        if self.energy <= 0:
            self.game.broadcast(
                '{} was killed by {}'.format(self.name, attacker))
            self.end('loser')
        else:
            self.update_gfx()

    def end(self, status):
        self.send_all('kill:{},{}'.format(status, self.name))
        del self.game.players[self.name]

    def send_all(self, msg):
        self.redis.publish(self.arena, msg)

    def update_gfx(self):
        self.motion_state.getWorldTransform(self.trans)
        pos_x = self.origin.getX()
        pos_y = self.origin.getY()
        pos_z = self.origin.getZ()
        quaternion = self.trans.getRotation()
        rot_x = quaternion.getX()
        rot_y = quaternion.getY()
        rot_z = quaternion.getZ()
        rot_w = quaternion.getW()
        msg = ('{name}:{pos_x},{pos_y},{pos_z},'
               '{rot_x:.2f},{rot_y:.2f},{rot_z:.2f},{rot_w:.2f},'
               '{energy:.1f},{avatar},{size_x},{size_y},{size_z},'
               '{scale},{color}').format(
            name=self.name,
            pos_x=int(pos_x),
            pos_y=int(pos_y),
            pos_z=int(pos_z),
            rot_x=rot_x,
            rot_y=rot_y,
            rot_z=rot_z,
            rot_w=rot_w,
            energy=self.energy,
            avatar=self.avatar,
            size_x=self.size_x,
            size_y=self.size_y,
            size_z=self.size_z,
            scale=self.scale,
            color=self.color
        )
        if msg != self.last_msg:
            print msg
            self.send_all(msg)
            self.last_msg = msg

    def wait_for_game(self):
        print("wait for game")
        while (self.game.started or self.game.finished or
               self.name not in self.game.players):
            gevent.sleep(1)
            try:
                uwsgi.websocket_recv_nb()
            except IOError:
                import sys
                print sys.exc_info()
                if self.name in self.players:
                    self.end('leaver')
                return [""]


class Robotab(Arena):

    def __call__(self, e, sr):
        if e['PATH_INFO'] == '/':
            sr('200 OK', [('Content-Type', 'text/html')])
            return [open('robotab_bullet.html').read()]

        if e['PATH_INFO'] == '/robotab_bullet.js':
            sr('200 OK', [('Content-Type', 'application/javascript')])
            return [open('static/js/robotab_bullet.js').read()]

        if e['PATH_INFO'] == '/robotab':
            uwsgi.websocket_handshake()
            username, avatar = uwsgi.websocket_recv().split(':')
            try:
                robot_coordinates = next(self.spawn_iterator)
            except StopIteration:
                self.spawn_iterator = iter(self.spawn_points)
                robot_coordinates = next(self.spawn_iterator)

            # uwsgi.websocket_send('posters:{}'.format(';'.join(self.posters)))

            for wall in self.walls_coordinates:
                uwsgi.websocket_send(
                    'wall:{},{},{},{},{},{},{}'.format(*wall))

            player = Player(self, username, avatar,
                            uwsgi.connection_fd(), *robot_coordinates)

            if(self.started or self.finished or
               len(self.players) > self.max_players or
               len(self.waiting_players) > 0):
                print('{}:{}:{}:{}'.format(
                    self.started, self.finished,
                    len(self.players) > self.max_players,
                    len(self.waiting_players) > 0))

                self.waiting_players.append(player)
                uwsgi.websocket_send(
                    "arena:hey {}, wait for next game".format(player.name))
                player.wait_for_game()
                self.waiting_players.remove(player)
            else:
                self.players[player.name] = player

            self.spawn_greenlets()

            player.update_gfx()

            for p in self.players.keys():
                uwsgi.websocket_send(self.players[p].last_msg)

            while True:
                ready = gevent.select.select(
                    [player.fd, player.redis_fd], [], [], timeout=4.0)

                if not ready[0]:
                    uwsgi.websocket_recv_nb()

                for fd in ready[0]:
                    if fd == player.fd:
                        try:
                            msg = uwsgi.websocket_recv_nb()
                        except IOError:
                            import sys
                            print sys.exc_info()
                            if player.name in self.players:
                                player.end('leaver')
                            return [""]
                        if msg and not self.finished:
                            self.msg_handler(player, msg)
                    elif fd == player.redis_fd:
                        msg = player.channel.parse_response()
                        if msg[0] == 'message':
                            uwsgi.websocket_send(msg[2])


application = Robotab()
