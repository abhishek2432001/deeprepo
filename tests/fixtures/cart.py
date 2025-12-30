"""
Shopping Cart Module

A simple shopping cart implementation.
"""

class ShoppingCart:
    """A cart for holding products."""
    
    def __init__(self):
        """Initialize empty cart."""
        self.items = []
        self.total = 0.0
    
    def add_item(self, name: str, price: float):
        """Add item to cart.
        
        Args:
            name: Product name
            price: Product price
        """
        self.items.append({"name": name, "price": price})
        self.total += price
    
    def get_total(self) -> float:
        """Get total price."""
        return self.total
