"""
E-commerce Shopping Cart System

This module implements a shopping cart for an online store.
"""

class ShoppingCart:
    """A shopping cart that holds products for purchase."""
    
    def __init__(self):
        """Initialize an empty shopping cart."""
        self.items = []
        self.total = 0.0
    
    def add_item(self, product_name: str, price: float, quantity: int = 1):
        """Add an item to the cart.
        
        Args:
            product_name: Name of the product
            price: Price per unit
            quantity: Number of units (default: 1)
        """
        item = {
            "name": product_name,
            "price": price,
            "quantity": quantity,
            "subtotal": price * quantity
        }
        self.items.append(item)
        self.total += item["subtotal"]
        print(f"Added {quantity}x {product_name} at ${price} each")
    
    def remove_item(self, product_name: str):
        """Remove an item from the cart by name.
        
        Args:
            product_name: Name of the product to remove
        """
        for item in self.items:
            if item["name"] == product_name:
                self.total -= item["subtotal"]
                self.items.remove(item)
                print(f"Removed {product_name}")
                return
        print(f"Item {product_name} not found in cart")
    
    def get_total(self) -> float:
        """Calculate the total price of all items.
        
        Returns:
            Total price as a float
        """
        return self.total
    
    def apply_discount(self, discount_percent: float):
        """Apply a percentage discount to the total.
        
        Args:
            discount_percent: Discount percentage (e.g., 10 for 10% off)
        """
        discount_amount = self.total * (discount_percent / 100)
        self.total -= discount_amount
        print(f"Applied {discount_percent}% discount: -${discount_amount:.2f}")
    
    def checkout(self):
        """Process checkout and display summary."""
        print("\n" + "=" * 50)
        print("CHECKOUT SUMMARY")
        print("=" * 50)
        for item in self.items:
            print(f"{item['quantity']}x {item['name']}: ${item['subtotal']:.2f}")
        print("-" * 50)
        print(f"TOTAL: ${self.total:.2f}")
        print("=" * 50)


# Example usage
if __name__ == "__main__":
    cart = ShoppingCart()
    cart.add_item("Laptop", 999.99, 1)
    cart.add_item("Mouse", 29.99, 2)
    cart.add_item("Keyboard", 79.99, 1)
    cart.apply_discount(10)
    cart.checkout()
