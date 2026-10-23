# SPDX-License-Identifier: GPL-3.0-or-later
"""Helper for the trigger shapes the base game specializations expect.

`addTrigger(node)` in the game only works on nodes with the trigger class, so
every `<... triggerNode="..."/>` / `<unloadingTrigger node="..."/>` / animal
loading trigger in our XMLs points to one of these box shapes.

The flag layout is copied from vanilla placeables: the trigger plays no role in
collision filtering except for the mask bits of the things it should notice.
"""

from meshlib import Mesh, box
from model import Node

# collision bits (see CollisionFlag in the game scripts)
PLAYER = 0x10000
VEHICLE = 0x100000
ANIMAL = 0x200000


def trigger_node(name, size, translation=(0.0, 0.0, 0.0), mask=PLAYER,
                 group="0x20000000"):
    """A static, invisible box trigger.

    size        (x, y, z) extent in metres
    translation centre of the box in the parent's space
    mask        collision flags the trigger reacts to
    """
    mesh = Mesh()
    mesh.add("collision", *box((0, 0, 0), size))
    return Node("Shape", name, mesh, materials=["collision"], **{
        "trigger": "true",
        "static": "true",
        "collisionFilterGroup": group,
        "collisionFilterMask": "0x%x" % mask,
        "castsShadows": "false",
        "receiveShadows": "false",
        "nonRenderable": "true",
        "translation": "%g %g %g" % tuple(translation),
    })


def trigger_mask(*flags):
    out = 0
    for f in flags:
        out |= f
    return out
