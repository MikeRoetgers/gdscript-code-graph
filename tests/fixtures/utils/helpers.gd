const Character = preload("res://actors/character.gd")

func is_alive(node: Node) -> bool:
    return node != null and node.health > 0
