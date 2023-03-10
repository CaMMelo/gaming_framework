import itertools
import sys
from random import randint
from uuid import uuid4

import pygame

from gaming_framework.geometry.shape import Circle, Point2D, Rectangle
from gaming_framework.physics.body import Body, CollisionHandler
from gaming_framework.physics.collision_shape import CollisionShape
from gaming_framework.physics.world import World
from gaming_framework.spatial_structures.quadtree import QuadTree

size = width, height = 320, 240


class Ball(CollisionHandler):
    def __init__(self, body: Body):
        self.body = body
        self.body.collision_handler = self
        self.collision_resolution_method_name = "resolve_collision_with_ball"
        self.id = uuid4()
        self.color = (255, 255, 255)

    def resolve_collision_with_ball(self, other):
        self.color = (255, 0, 0) if self.color == (255, 255, 255) else (255, 255, 255)

    def update(self, delta_time):
        if self.body.position.x + self.body.shape.radius >= width:
            self.body.speed = Point2D(-self.body.speed.x, self.body.speed.y)
        if self.body.position.x - self.body.shape.radius <= 0:
            self.body.speed = Point2D(-self.body.speed.x, self.body.speed.y)
        if self.body.position.y + self.body.shape.radius >= height:
            self.body.speed = Point2D(self.body.speed.x, -self.body.speed.y)
        if self.body.position.y - self.body.shape.radius <= 0:
            self.body.speed = Point2D(self.body.speed.x, -self.body.speed.y)
        position = Point2D(
            max(
                0 + self.body.shape.radius,
                min(width - self.body.shape.radius, self.body.position.x),
            ),
            max(
                0 - self.body.shape.radius,
                min(height - self.body.shape.radius - 1e-10, self.body.position.y),
            ),
        )
        if position != self.body.position:
            self.body.move_to(position)

    def draw(self, screen):
        pygame.draw.circle(
            screen, self.color, self.body.position, self.body.shape.radius, 1
        )


area = Rectangle(Point2D(0, height), Point2D(width, 0))
quadtree = QuadTree(area)
world = World(area, quadtree)

circles = []
ncols = 6
nlines = 5
speed_factor = 1 / 4
w = width / ncols
h = height / nlines
for col, line in itertools.product(range(ncols), range(nlines)):
    center = Point2D((col * w + w / 2), (line * h + h / 2))
    circle = Circle(center, randint(5, 10))
    circles.append(circle)
bodies = [
    Body(
        collision_shape=CollisionShape(circle),
        speed=Point2D(
            (randint(500, 600) / circle.radius) * (-1) ** randint(0, 1) * speed_factor,
            (randint(500, 600) / circle.radius) * (-1) ** randint(0, 1) * speed_factor,
        ),
        mass=circle.radius,
    )
    for circle in circles
]
balls = [Ball(body) for body in bodies]

for body in bodies:
    quadtree.insert(body)


pygame.init()


screen = pygame.display.set_mode((width, height))


previous_tick = 0
while True:
    current_tick = pygame.time.get_ticks()
    delta_time = (current_tick - previous_tick) / 1000
    previous_tick = current_tick

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()

    world.update(delta_time)
    for ball in balls:
        ball.update(delta_time)

    screen.fill((0, 0, 0))
    for ball in balls:
        ball.draw(screen)
    pygame.display.flip()
