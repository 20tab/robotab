from random import choice, randrange

import uwsgi
import gevent
import gevent.queue
import gevent.event
import gevent.select
import redis
import math
import ode


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
        self.finished = False
        #self.warming_up = False
        self.walls = (
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
            #    x,     y,               r,    color
            #(    0,  1650,         math.pi),
            #(    0, -1650,               0),
            ( -935,   935, 3 * math.pi / 4, 0x7777AA),
            (  935,   935, 5 * math.pi / 4, 0x770000),
            (  935,  -935, 7 * math.pi / 4, 0x007700),
            ( -935,  -935,     math.pi / 4, 0x777700),
            (-1650,  1650, 3 * math.pi / 4, 0xAA00AA),
            #(-1650,     0,     math.pi / 2),
            #( 1650,     0, 3 * math.pi / 2),
            ( 1650,  1650, 5 * math.pi / 4, 0x007777),
            ( 1650, -1650, 7 * math.pi / 4, 0x000077),
            (-1650, -1650,     math.pi / 4, 0xFFAA77),

        )
        self.world = ode.World()
        self.world.setGravity((0, -9.81, 0))
        self.space = ode.Space()
        self.floor = ode.GeomPlane(self.space, (0, 0, 1), 0)
        self.contactgroup = ode.JointGroup()
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

    def near_callback(self, args, geom1, geom2):
        # Check if the objects do collide
        contacts = ode.collide(geom1, geom2)

        # Create contact joints
        world, contactgroup = args
        for c in contacts:
            c.setBounce(0.2)
            c.setMu(5000)
            j = ode.ContactJoint(world, contactgroup, c)
            j.attach(geom1.getBody(), geom2.getBody())

    def broadcast(self, msg):
        self.redis.publish(self.arena, 'arena:{}'.format(msg))

    def msg_handler(self, player, msg):
        p, cmd = msg.split(':')
        if cmd not in ('at', 'AT'):
            self.players[p].cmd = cmd

    def cmd_handler(self, player, cmd):
        if cmd == 'rl':
            #player.arena_object.rotateL()
            return True

        if cmd == 'rr':
            #player.arena_object.rotateR()
            return True

        if cmd == 'fw':
            print('fw')
            player.body.addForce((0.0, 0.0, 100.0))
            return True

        if cmd == 'bw':
            print("bw")
            player.body.addForce((0.0, 0.0, -100.0))
            return True

        return False

    def engine_start(self):
        del self.greenlets['engine']
        print('engine started')
        while True:
            if len(self.players) == 1 and self.started:
                self.finished = True
                self.winning_logic()
                self.restart_game(11)
                break
            elif len(self.players) == 0:
                self.finished = True
                self.restart_game()
                break
            t = uwsgi.micros() / 1000.0
            self.space.collide(
                (self.world, self.contactgroup), self.near_callback)
            for p in self.players.keys():
                player = self.players[p]
                if player.cmd:
                    draw = self.cmd_handler(player, player.cmd)
                    draw = True
                    if draw:
                        player.update_gfx()
                    player.cmd = None
            self.world.step(1.0/30.0)
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
            for p in self.players.keys():
                self.players[p].update_gfx()
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


class Player(object):

    def __init__(self, game, name, avatar, fd, x, y, r, color, speed=15):
        self.game = game
        self.name = name
        self.avatar = avatar
        self.fd = fd

        self.body = ode.Body(self.game.world)
        M = ode.Mass()
        M.setSphere(2500.0, 8.0)
        M.mass = 900.0
        self.body.setMass(M)
        self.geom = ode.GeomSphere(game.space, 8.0)
        self.geom.setBody(self.body)

        #self.arena_object = ArenaObject(x, y, r, speed)
        self.body.setPosition((x, 100.0, y))
        self.r = r

        self.attack = 0
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
                '{} was killed by {}'.format(self.name, attacker)
            )
            self.end('loser')
        else:
            self.update_gfx()

    def end(self, status):
        self.send_all('kill:{},{}'.format(status, self.name))
        del self.game.players[self.name]

    def send_all(self, msg):
        self.redis.publish(self.arena, msg)

    def update_gfx(self):
        x, y, z = self.body.getPosition()
        msg = "{}:{},{},{},{},{},{},{},{},{}".format(
            self.name,
            self.r,
            #self.arena_object.r,
            x,
            y,
            z,
            self.attack,
            self.energy,
            self.avatar,
            #self.arena_object.scale,
            8,
            self.color
        )
        self.send_all(msg)

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
            return [open('robotab_ws.html').read()]

        if e['PATH_INFO'] == '/robotab.js':
            sr('200 OK', [('Content-Type', 'application/javascript')])
            return [open('static/js/robotab.js').read()]

        if e['PATH_INFO'] == '/robotab':
            uwsgi.websocket_handshake()
            username, avatar = uwsgi.websocket_recv().split(':')
            try:
                robot_coordinates = self.spawn_iterator.next()
            except StopIteration:
                self.spawn_iterator = iter(self.spawn_points)
                robot_coordinates = self.spawn_iterator.next()

            uwsgi.websocket_send('posters:{}'.format(';'.join(self.posters)))
            uwsgi.websocket_send('walls:{}'.format(str(self.walls).replace('),', ';').translate(None, "()")))
            player = Player(self, username, avatar,
                            uwsgi.connection_fd(), *robot_coordinates)

            if(self.started or self.finished or
               len(self.players) > self.max_players or
               len(self.waiting_players) > 0):
                # print('{}:{}:{}:{}'.format(self.started, self.finished, len(self.players) > self.max_players, len(self.waiting_players) > 0))
                self.waiting_players.append(player)
                uwsgi.websocket_send(
                    "arena:hey {}, wait for next game".format(player.name))
                player.wait_for_game()
                self.waiting_players.remove(player)
            else:
                self.players[player.name] = player

            self.spawn_greenlets()

            for p in self.players.keys():
                self.players[p].update_gfx()

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
