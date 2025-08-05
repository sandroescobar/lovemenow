# LoveMeNow Inventory Management System

## Overview
The inventory management system ensures that products are properly tracked and that inventory is only decremented when actual purchases are completed through Stripe payments.

## Key Features

### 1. Product Availability Check
- Products are considered available only when `in_stock = True` AND `quantity_on_hand > 0`
- New `is_available` property provides a single check for product availability
- Frontend templates updated to use `product.is_available` instead of separate checks

### 2. Cart Validation
- **Add to Cart**: Only available products can be added to cart
- **Quantity Limits**: Users cannot add more items than available in stock
- **Stock Warnings**: Clear error messages when stock limits are reached
- **Out of Stock**: "Add to Cart" button becomes "Out of Stock" and is disabled

### 3. Inventory Decrement
- **Timing**: Inventory is ONLY decremented after successful Stripe payment
- **Webhook Processing**: Stripe webhooks handle inventory updates
- **Atomic Operations**: Uses database transactions to ensure consistency
- **Error Handling**: Graceful handling of insufficient stock scenarios

### 4. Wishlist Support
- Users can add out-of-stock items to their wishlist
- Wishlist functionality remains available even when products are out of stock

## Technical Implementation

### Database Changes
- Enhanced `Product` model with new methods:
  - `is_available`: Property that checks both `in_stock` and `quantity_on_hand`
  - `can_add_to_cart()`: Validates if quantity can be added to cart
  - `decrement_inventory()`: Safely decrements stock and updates status

### Frontend Updates
- **Templates**: Updated to use `product.is_available`
- **JavaScript**: Enhanced quick view modal to handle stock status
- **Cart Display**: Shows current stock levels and availability

### Backend Updates
- **Cart Routes**: Enhanced validation using new Product methods
- **API Endpoints**: Updated to return proper stock information
- **Webhooks**: Stripe webhook handler decrements inventory on successful payment

### Webhook Integration
- **Metadata Storage**: Cart information stored in Stripe session metadata
- **Guest Support**: Works for both authenticated and guest users
- **Inventory Processing**: Decrements stock for each purchased item
- **Status Updates**: Automatically marks products as out-of-stock when quantity reaches 0

## Usage

### For Developers

#### Check Product Availability
```python
if product.is_available:
    # Product can be purchased
    pass
else:
    # Product is out of stock
    pass
```

#### Validate Cart Addition
```python
can_add, message = product.can_add_to_cart(requested_qty, current_cart_qty)
if not can_add:
    return jsonify({'error': message}), 400
```

#### Decrement Inventory (in webhooks only)
```python
success = product.decrement_inventory(quantity)
if success:
    db.session.commit()
```

### For Administrators

#### Inventory Management Tool
```bash
# List all products and their stock levels
python3 inventory_manager.py list

# Update specific product stock
python3 inventory_manager.py update <product_id> <new_quantity>

# Restock all products to 10 units
python3 inventory_manager.py restock 10

# Find out-of-stock products
python3 inventory_manager.py out-of-stock
```

#### Testing
```bash
# Run inventory system tests
python3 test_inventory.py
```

## Workflow

### Customer Purchase Flow
1. **Browse Products**: Only in-stock products show "Add to Cart"
2. **Add to Cart**: System validates stock availability
3. **Checkout**: Stripe session created with cart metadata
4. **Payment**: Customer completes payment through Stripe
5. **Webhook**: Stripe sends payment confirmation
6. **Inventory Update**: System decrements stock for purchased items
7. **Status Update**: Products with 0 stock marked as out-of-stock

### Stock Management Flow
1. **Initial State**: Products have `quantity_on_hand` and `in_stock = True`
2. **Purchase**: Webhook decrements `quantity_on_hand`
3. **Out of Stock**: When `quantity_on_hand = 0`, `in_stock = False`
4. **Restock**: Admin updates `quantity_on_hand` and `in_stock = True`

## Error Handling

### Insufficient Stock
- Cart validation prevents over-ordering
- Clear error messages to users
- Webhook handles edge cases gracefully

### Race Conditions
- Database transactions ensure consistency
- Webhook processing is idempotent
- Stock checks at multiple validation points

### Guest Users
- Cart data stored in Stripe session metadata
- Inventory decremented same as authenticated users
- No data loss during checkout process

## Configuration

### Environment Variables
```env
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

### Webhook Endpoint
- URL: `https://yourdomain.com/webhooks/stripe`
- Events: `checkout.session.completed`
- Method: POST

## Monitoring

### Stock Alerts
- Use `inventory_manager.py out-of-stock` to find low stock
- Monitor webhook logs for inventory updates
- Track successful vs failed inventory decrements

### Performance
- Database queries optimized with proper indexing
- Webhook processing is lightweight and fast
- Cart validation happens at multiple checkpoints

## Security

### Webhook Verification
- All webhooks verified using Stripe signature
- Invalid webhooks rejected automatically
- Inventory only updated for verified payments

### Data Integrity
- Atomic database transactions
- Rollback on errors
- Consistent state maintained

This system ensures that your inventory is accurately tracked and that customers cannot purchase items that are out of stock, while providing a smooth shopping experience.