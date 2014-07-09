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

    def __init__(self, world, size_x, size_y, size_z, x, y, z, r, friction=0.5, sc_x=1, sc_y=1, sc_z=1):
        self.shape = BoxShape(Vector3(size_x*sc_x, size_y*sc_y, size_z*sc_z))
        q = Quaternion(0, 0, 0, 1)
        q.setRotation(Vector3(0.0, 1.0, 0.0), r)
        self.motion_state = DefaultMotionState(
            Transform(q, Vector3(x, y, z)))
        construction_info = RigidBodyConstructionInfo(
            0, self.motion_state, self.shape, Vector3(0, 0, 0))
        construction_info.m_friction = friction
        self.body = RigidBody(construction_info)
        world.addRigidBody(self.body)


class Box(object):

    def __init__(self, game, mass, size_x, size_y, size_z, x, y, z, r, friction=0.5, sc_x=1, sc_y=1, sc_z=1):
        self.game = game
        self.mass = mass
        self.shape = BoxShape(Vector3(size_x*sc_x, size_y*sc_y, size_z*sc_z))
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
            'start': self.start
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
        self.finished = gevent.event.Event()
        #self.warming_up = False
        self.walls = []
        self.ground_coordinates = (2000, 1, 2000, 0, 0, 0, 0)
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
            ( -935,    50,   935,  3 * math.pi / 4, 0x7777AA),
            (  935,    50,   935,  5 * math.pi / 4, 0x770000),
            (  935,    50,  -935,  7 * math.pi / 4, 0x007700),
            ( -935,    50,  -935,      math.pi / 4, 0x777700),
            (-1650,    50,  1650,  3 * math.pi / 4, 0xAA00AA),
            #(-1650,     0,     math.pi / 2),
            #( 1650,     0, 3 * math.pi / 2),
            ( 1650,    50,  1650,  5 * math.pi / 4, 0x007777),
            ( 1650,    50, -1650,  7 * math.pi / 4, 0x000077),
            (-1650,    50, -1650,      math.pi / 4, 0xFFAA77),

        )

        self.broadphase = DbvtBroadphase()
        self.collisionConfiguration = DefaultCollisionConfiguration()
        self.dispatcher = CollisionDispatcher(self.collisionConfiguration)
        self.solver = SequentialImpulseConstraintSolver()
        self.world = DiscreteDynamicsWorld(
            self.dispatcher, self.broadphase,
            self.solver, self.collisionConfiguration)
        self.world.setGravity(Vector3(0, -9.81, 0))

        self.ground = StaticBox(self.world, *self.ground_coordinates)

        for wall_c in self.walls_coordinates:
            wall = StaticBox(self.world, wall_c[0], wall_c[1], 6, wall_c[3], 0, wall_c[5], wall_c[6], 5.0, 10, 1, 6)
            self.walls.append(wall)

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
        if cmd != 'AT':
            self.players[p].cmd = cmd

    def cmd_handler(self, player, cmd):
        if cmd == 'rl':
            q = Quaternion(0, 0.05, 0, 1) * player.trans.getRotation()
            player.trans.setRotation(q)
            player.body.activate(True)
            player.body.setCenterOfMassTransform(player.trans)
            #player.body.activate(True)
            #player.body.setWorldTransform(player.trans)
            #orientation = player.body.getOrientation()
            #v = Vector3(0, 1000, 0).rotate(
            #    orientation.getAxis(), orientation.getAngle())
            #player.body.activate(True)
            #player.body.applyTorqueImpulse(v)
            return True

        if cmd == 'rr':
            q = Quaternion(0, -0.05, 0, 1) * player.trans.getRotation()
            player.trans.setRotation(q)
            player.body.activate(True)
            player.body.setCenterOfMassTransform(player.trans)
            #orientation = player.body.getOrientation()
            #v = Vector3(0, -1000, 0).rotate(
            #    orientation.getAxis(), orientation.getAngle())
            #player.body.activate(True)
            #player.body.applyTorqueImpulse(v)
            return True

        if cmd == 'fw':
            #player.vehicle.applyEngineForce(100000.0, 2)
            #player.vehicle.applyEngineForce(100000.0, 3)

            orientation = player.body.getOrientation()
            v = Vector3(0, 0, 6000).rotate(
                orientation.getAxis(), orientation.getAngle())
            player.body.activate(True)
            player.body.applyCentralForce(v)
            return True

        if cmd == 'bw':
            orientation = player.body.getOrientation()
            v = Vector3(0, 0, -6000).rotate(
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
                self.finished.set()
                self.winning_logic()
                self.restart_game(2)
                break
            elif len(self.players) == 0:
                self.finished.set()
                self.restart_game()
                break

            self.world.stepSimulation(1, 30)
            for p in self.players.keys():
                player = self.players[p]
                velocity = player.body.getLinearVelocity()
                speed = velocity.length()
                if speed > player.max_speed:
                    new_speed = player.max_speed / speed
                    velocity = Vector3(
                        new_speed * velocity.getX(),
                        new_speed * velocity.getY(),
                        new_speed * velocity.getZ())
                    player.body.setLinearVelocity(velocity)
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
            # for p in self.players:
            #     self.players[p].update_gfx()
            gevent.sleep(1)
            if self.finished.is_set():
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
        self.finished.wait(timeout=10.0)
        while not self.finished.is_set():
            # if len(self.bonus_malus_spawn_points) > 0:
            #     coordinates = self.bonus_malus_spawn_points.pop(randrange(len(self.bonus_malus_spawn_points)))
            #     choice(self.bonus_malus)(self, bm_counter, *(coordinates))
            #     bm_counter += 1
            self.finished.wait(timeout=10.0)
        self.broadcast("end")
        self.started = False
        self.greenlets['start'] = self.start
        print("end")
        #gevent.sleep()

    def spawn_greenlets(self):
        for greenlet in self.greenlets.keys():
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
        while countdown > 0:
            self.broadcast(
                'next game will start in {} seconds'.format(countdown))
            countdown -= 1
            gevent.sleep(1)
        #self.finished.clear()
        self.players = {}
        print('\n\n', self.waiting_players, '\n\n')
        if len(self.waiting_players) > 0:
            for player in self.waiting_players:
                self.players[player.name] = player
                if len(self.players) >= self.max_players:
                    break
        self.finished.clear()
        self.broadcast('waiting for players')


class Player(Box):

    def __init__(self, game, name, avatar, fd, x, y, z, r, color, max_speed=80):
        self.sc_x = 5
        self.sc_y = 5
        self.sc_z = 5
        super(Player, self).__init__(game, 900.0, 6, 7, 9, x, y, z, r, 0.5, self.sc_x, self.sc_y, self.sc_z)
        self.name = name
        self.avatar = avatar
        self.fd = fd
        self.tuning = VehicleTuning()
        self.vehicle_ray_caster = DefaultVehicleRaycaster(game.world)
        self.vehicle = RaycastVehicle(self.tuning, self.body, self.vehicle_ray_caster)
        #self.game.world.addVehicle(self.vehicle)
        wheel_width = 1
        wheel_radius = 1
        wheel_direction = Vector3(0, -1, 0)
        wheel_axle = Vector3(-1, 0, 0)
        suspension_rest_length = 0.6
        is_front_wheel = True 
        connection_height = 1.8
        connection_point = Vector3(1-(0.3*wheel_width), connection_height, 2*1-wheel_radius)
        self.vehicle.addWheel(connection_point, wheel_direction, wheel_axle, suspension_rest_length, wheel_radius, self.tuning, is_front_wheel)
        connection_point = Vector3(-1+(0.3*wheel_width), connection_height, 2*1-wheel_radius)
        self.vehicle.addWheel(connection_point, wheel_direction, wheel_axle, suspension_rest_length, wheel_radius, self.tuning, is_front_wheel)
        is_front_wheel = False
        connection_point = Vector3(-1+(0.3*wheel_width), connection_height, -2*1+wheel_radius)
        self.vehicle.addWheel(connection_point, wheel_direction, wheel_axle, suspension_rest_length, wheel_radius, self.tuning, is_front_wheel)
        connection_point = Vector3(1-(0.3*wheel_width), connection_height, -2*1+wheel_radius)
        self.vehicle.addWheel(connection_point, wheel_direction, wheel_axle, suspension_rest_length, wheel_radius, self.tuning, is_front_wheel)
        self.last_msg = None

        # self.attack = 0
        self.energy = 100.0
        self.arena = "arena{}".format(uwsgi.worker_id())
        self.redis = redis.StrictRedis()
        self.channel = self.redis.pubsub()
        self.channel.subscribe(self.arena)
        self.redis_fd = self.channel.connection._sock.fileno()

        self.cmd = None
        self.max_speed = max_speed
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
               '{energy:.1f},{avatar},{sc_x},{sc_y},{sc_z},{color}').format(
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
            sc_x=self.sc_x,
            sc_y=self.sc_y,
            sc_z=self.sc_z,
            color=self.color
        )
        if msg != self.last_msg:
            #print msg
            self.send_all(msg)
            self.last_msg = msg

    def wait_for_game(self):
        print("wait for game")
        while (self.game.started or self.game.finished.is_set() or
               self.name not in self.game.players):
            gevent.sleep(1)
            try:
                uwsgi.websocket_recv_nb()
            except IOError:
                import sys
                print sys.exc_info()
                if self.name in self.game.players:
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

            uwsgi.websocket_send('posters:{}'.format(';'.join(self.posters)))

            for wall in self.walls_coordinates:
                uwsgi.websocket_send(
                    'wall:{},{},{},{},{},{},{}'.format(*wall))

            player = Player(self, username, avatar,
                            uwsgi.connection_fd(), *robot_coordinates)

            if(self.started or self.finished.is_set() or
               len(self.players) > self.max_players or
               len(self.waiting_players) > 0):
                #print('{}:{}:{}:{}'.format(
                #    self.started, self.finished,
                #    len(self.players) > self.max_players,
                #    len(self.waiting_players) > 0))

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
                        if msg and not self.finished.is_set():
                            self.msg_handler(player, msg)
                    elif fd == player.redis_fd:
                        msg = player.channel.parse_response()
                        if msg[0] == 'message':
                            uwsgi.websocket_send(msg[2])


application = Robotab()
