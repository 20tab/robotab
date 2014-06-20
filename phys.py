import ode
import math
import redis
import uwsgi
import gevent


class Box(object):
    def __init__(self, name, world, weight, size):
        self.body = ode.Body(world.world)
        M = ode.Mass()
        M.setBox(2500, size, size, size)
        M.mass = weight
        self.body.setMass(M)
        self.geom = ode.GeomBox(world.space, lengths=(size, size, size))
        self.geom.setBody(self.body)
        world.boxes[name] = self
        self.name = name
        self.rx = 0
        self.ry = 0
        self.rz = 0
        self.size = size
        self.last_msg = None
        self.world = world

    def rotateY(self, amount):
        self.ry += amount
        self.geom.setQuaternion((1.0, self.rx, self.ry, self.rz))

    def set_pos(self, x, y, z):
        self.body.setPosition((x, y, z))

    def draw(self):
        pos_x,pos_y,pos_z = self.body.getPosition()
        rot_w,rot_x,rot_y,rot_z = self.body.getQuaternion()
        msg = '{name}:{pos_x},{pos_y},{pos_z:},{size_x},{size_y},{size_z},{rot_x:.2f},{rot_y:.2f},{rot_z:.2f}'.format(
            name=self.name,
            pos_x=int(pos_x),
            pos_y=int(pos_y),
            pos_z=int(pos_z),
            size_x=self.size,
            size_y=self.size,
            size_z=self.size,
            rot_x=rot_x,
            rot_y=rot_y,
            rot_z=rot_z,
        )
        if msg != self.last_msg:
            if msg.startswith('box0'):
                print msg
            self.world.redis.publish('phys', msg)
            self.last_msg = msg


class World(object):
    def __init__(self):
        self.world = ode.World()
        self.world.setGravity( (0,-9.81,0) )
        self.space = ode.Space()
        self.boxes = {}
        self.contactgroup = ode.JointGroup()
        self.redis = redis.StrictRedis()
        self.redis_pubsub = redis.StrictRedis()
        self.channel = self.redis_pubsub.pubsub()
        self.channel.subscribe('phys')
        self.redis_fd = self.channel.connection._sock.fileno()
        self.floor = ode.GeomPlane(self.space, (0,1,0), 0)

def near_callback(args, geom1, geom2):
    contacts = ode.collide(geom1, geom2)
    world,contactgroup = args
    for c in contacts:
        c.setBounce(0.1)
        c.setMu(10000)
        j = ode.ContactJoint(world, contactgroup, c)
        j.attach(geom1.getBody(), geom2.getBody())


def physic_engine(world):
    while True:
        t = uwsgi.micros() / 1000.0
        world.space.collide((world.world, world.contactgroup), near_callback)
        for name,box in world.boxes.items():
            box.draw()
        world.world.step(1)
        world.contactgroup.empty()
        t1 = uwsgi.micros() / 1000.0
        delta = t1 - t
        if delta < 33.33:
            gevent.sleep((33.33 - delta) / 1000.0)


def application(e, sr):
    if e['PATH_INFO'] == '/phys':
        uwsgi.websocket_handshake()

        w = World()
        me = Box('box0', w, 900, 200)
        me.set_pos(0, 1150, 0)
        box1 = Box('box1', w, 20, 50)
        box1.set_pos(0, 250, 0)
        box2 = Box('box2', w, 20, 50)
        box2.set_pos(0, 350, 0)
        box3 = Box('box3', w, 20, 50)
        box3.set_pos(0, 450, 0)
        box4 = Box('box4', w, 200, 150)
        box4.set_pos(0, 550, 0)


        gevent.spawn(physic_engine, w)
        ufd = uwsgi.connection_fd()
        while True:

            ready = gevent.select.select([ufd, w.redis_fd], [], [], timeout=4.0)

            if not ready[0]:
                uwsgi.websocket_recv_nb()

            for fd in ready[0]:
                if fd == ufd:
                    try:
                        msg = uwsgi.websocket_recv_nb()
                        if msg == 'fw':
                            me.body.addForce((0, 250, 0))
                    except IOError:
                        import sys
                        print sys.exc_info()
                        return [""]
                elif fd == w.redis_fd:
                    msg = w.channel.parse_response()
                    if msg[0] == 'message':
                        uwsgi.websocket_send(msg[2])

