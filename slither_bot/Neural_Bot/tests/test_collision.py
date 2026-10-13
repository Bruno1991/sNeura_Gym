"""Testes unitários para o sistema de colisões."""

import unittest

from slither_ai.core.collision import SlitherCollision
from slither_ai.core.entities import Food, Snake


class TestSlitherCollision(unittest.TestCase):
    def test_boundary_collision(self):
        inside_snake = Snake(snake_id=1, x=500.0, y=500.0)
        self.assertFalse(SlitherCollision.check_boundary_collision(inside_snake, arena_radius=2000.0))

        outside_snake = Snake(snake_id=2, x=2050.0, y=0.0)
        self.assertTrue(SlitherCollision.check_boundary_collision(outside_snake, arena_radius=2000.0))

    def test_food_consumption(self):
        snake = Snake(snake_id=1, x=100.0, y=100.0, initial_score=10.0)
        food_close = Food(id=1, x=105.0, y=105.0, value=2.0)
        food_far = Food(id=2, x=600.0, y=600.0, value=1.0)

        eaten = SlitherCollision.check_food_consumption(snake, [food_close, food_far])
        self.assertEqual(len(eaten), 1)
        self.assertEqual(eaten[0].id, 1)
        self.assertTrue(food_close.is_eaten)
        self.assertFalse(food_far.is_eaten)
        self.assertEqual(snake.score, 12.0)

    def test_snake_body_collision(self):
        # Cobra B tem um segmento em (200, 200)
        snake_b = Snake(snake_id=2, x=200.0, y=200.0)
        snake_b.segments[0].x = 200.0
        snake_b.segments[0].y = 200.0

        # Cobra A bate de cabeça no segmento da Cobra B
        snake_a = Snake(snake_id=1, x=200.0, y=200.0)

        deaths = SlitherCollision.check_snake_collisions([snake_a, snake_b])
        self.assertTrue(any(victim.id == snake_a.id for victim, _ in deaths))


if __name__ == "__main__":
    unittest.main()
