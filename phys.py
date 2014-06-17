# pyODE example 1: Getting started
    
import ode

def near_callback(args, geom1, geom2):
    """Callback function for the collide() method.

    This function checks if the given geoms do collide and
    creates contact joints if they do.
    """

    # Check if the objects do collide
    contacts = ode.collide(geom1, geom2)

    # Create contact joints
    world,contactgroup = args
    for c in contacts:
        c.setBounce(0.2)
        c.setMu(5000)
        j = ode.ContactJoint(world, contactgroup, c)
        j.attach(geom1.getBody(), geom2.getBody())

# Create a world object
world = ode.World()
world.setGravity( (0,-9.81,0) )

space = ode.Space()
floor = ode.GeomPlane(space, (0,1,0), 0)

# Create a body inside the world
body = ode.Body(world)
M = ode.Mass()
M.setSphere(2500.0, 0.05)
M.mass = 900.0
body.setMass(M)
#body.setGravityMode(False)

geom = ode.GeomSphere(space, 0.05)
geom.setBody(body)

body.setPosition( (0,2,0) )
body.addForce( (0.01, 0,0) )

contactgroup = ode.JointGroup()

# Do the simulation...
total_time = 0.0
dt = 1.0/30
while True:
    space.collide((world,contactgroup), near_callback)

    #body.addForce( (0.01, 0,0) )
    x,y,z = body.getPosition()
    u,v,w = body.getLinearVel()
    print "%1.2fsec: pos=(%6.3f, %6.3f, %6.3f)  vel=(%6.3f, %6.3f, %6.3f)" % \
          (total_time, x, y, z, u,v,w)
    world.step(dt)
    total_time+=dt
    #print contactgroup
    contactgroup.empty()

