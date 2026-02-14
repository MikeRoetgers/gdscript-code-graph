extends Node2D
class_name Character

var health: int = 100

func take_damage(amount: int):
    health -= amount
    if health <= 0:
        queue_free()

func get_bullet() -> Bullet:
    return null
