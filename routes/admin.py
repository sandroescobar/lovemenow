"""
Admin routes for LoveMeNow application
"""
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc, func
from datetime import datetime, timedelta

from routes import db
from models import User, Product, Order, AuditLog, Cart, Wishlist
from security import admin_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard"""
    try:
        # Get basic statistics
        total_users = User.query.count()
        total_products = Product.query.count()
        total_orders = Order.query.count()
        
        # Get recent orders
        recent_orders = Order.query.order_by(desc(Order.created_at)).limit(10).all()
        
        # Get recent audit logs
        recent_logs = AuditLog.query.order_by(desc(AuditLog.created_at)).limit(20).all()
        
        # Get user registration stats for the last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        new_users_count = User.query.filter(User.created_at >= thirty_days_ago).count()
        
        return render_template('admin/dashboard.html',
                             total_users=total_users,
                             total_products=total_products,
                             total_orders=total_orders,
                             recent_orders=recent_orders,
                             recent_logs=recent_logs,
                             new_users_count=new_users_count)
    
    except Exception as e:
        current_app.logger.error(f"Admin dashboard error: {str(e)}")
        return render_template('errors/500.html'), 500

@admin_bp.route('/order-management')
@login_required
@admin_required
def order_management():
    """Order management interface with real-time tracking"""
    try:
        return render_template('admin_orders.html')
    except Exception as e:
        current_app.logger.error(f"Admin order management error: {str(e)}")
        return render_template('errors/500.html'), 500

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """User management page"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        users = User.query.order_by(desc(User.created_at)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('admin/users.html', users=users)
    
    except Exception as e:
        current_app.logger.error(f"Admin users page error: {str(e)}")
        return render_template('errors/500.html'), 500

@admin_bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    """Audit logs page"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        action_filter = request.args.get('action', '')
        status_filter = request.args.get('status', '')
        
        query = AuditLog.query
        
        if action_filter:
            query = query.filter(AuditLog.action.contains(action_filter))
        
        if status_filter:
            query = query.filter(AuditLog.status == status_filter)
        
        logs = query.order_by(desc(AuditLog.created_at)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('admin/audit_logs.html', 
                             logs=logs, 
                             action_filter=action_filter,
                             status_filter=status_filter)
    
    except Exception as e:
        current_app.logger.error(f"Admin audit logs page error: {str(e)}")
        return render_template('errors/500.html'), 500

@admin_bp.route('/orders')
@login_required
@admin_required
def orders():
    """Orders management page"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        status_filter = request.args.get('status', '')
        
        query = Order.query
        
        if status_filter:
            query = query.filter(Order.status == status_filter)
        
        orders = query.order_by(desc(Order.created_at)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('admin/orders.html', 
                             orders=orders,
                             status_filter=status_filter)
    
    except Exception as e:
        current_app.logger.error(f"Admin orders page error: {str(e)}")
        return render_template('errors/500.html'), 500

@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """API endpoint for dashboard statistics"""
    try:
        # Get various statistics
        stats = {
            'total_users': User.query.count(),
            'total_products': Product.query.count(),
            'total_orders': Order.query.count(),
            'active_carts': Cart.query.distinct(Cart.user_id).count(),
            'wishlist_items': Wishlist.query.count(),
        }
        
        # Get recent activity counts
        last_24h = datetime.utcnow() - timedelta(hours=24)
        stats['recent_registrations'] = User.query.filter(User.created_at >= last_24h).count()
        stats['recent_orders'] = Order.query.filter(Order.created_at >= last_24h).count()
        stats['recent_logins'] = AuditLog.query.filter(
            AuditLog.action == 'user_login',
            AuditLog.created_at >= last_24h
        ).count()
        
        return jsonify(stats)
    
    except Exception as e:
        current_app.logger.error(f"Admin API stats error: {str(e)}")
        return jsonify({'error': 'Failed to fetch statistics'}), 500

@admin_bp.route('/api/user/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_user_admin(user_id):
    """Toggle admin status for a user"""
    try:
        if current_user.id == user_id:
            return jsonify({'error': 'Cannot modify your own admin status'}), 400
        
        user = User.query.get_or_404(user_id)
        user.is_admin = not user.is_admin
        db.session.commit()
        
        # Log the admin action
        AuditLog.log_action(
            action='admin_role_changed',
            user_id=current_user.id,
            resource_type='user',
            resource_id=user_id,
            details=f'Admin {current_user.email} {"granted" if user.is_admin else "revoked"} admin privileges for {user.email}',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            status='success'
        )
        
        return jsonify({
            'message': f'Admin status {"granted" if user.is_admin else "revoked"} for {user.email}',
            'is_admin': user.is_admin
        })
    
    except Exception as e:
        current_app.logger.error(f"Toggle admin error: {str(e)}")
        return jsonify({'error': 'Failed to update admin status'}), 500

@admin_bp.route('/api/user/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    """Toggle active status for a user"""
    try:
        if current_user.id == user_id:
            return jsonify({'error': 'Cannot modify your own active status'}), 400
        
        user = User.query.get_or_404(user_id)
        user.active = not user.active
        db.session.commit()
        
        # Log the admin action
        AuditLog.log_action(
            action='user_status_changed',
            user_id=current_user.id,
            resource_type='user',
            resource_id=user_id,
            details=f'Admin {current_user.email} {"activated" if user.active else "deactivated"} user {user.email}',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            status='success'
        )
        
        return jsonify({
            'message': f'User {"activated" if user.active else "deactivated"}: {user.email}',
            'active': user.active
        })
    
    except Exception as e:
        current_app.logger.error(f"Toggle user active error: {str(e)}")
        return jsonify({'error': 'Failed to update user status'}), 500

@admin_bp.route('/security')
@login_required
@admin_required
def security_monitoring():
    """Security monitoring dashboard"""
    try:
        # Get security-related audit logs from the last 7 days
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Get suspicious activities
        suspicious_logs = AuditLog.query.filter(
            AuditLog.action.in_(['suspicious_request', 'rate_limit_exceeded', 'age_verification_denied']),
            AuditLog.created_at >= seven_days_ago
        ).order_by(desc(AuditLog.created_at)).limit(50).all()
        
        # Get failed login attempts
        failed_logins = AuditLog.query.filter(
            AuditLog.action == 'user_login',
            AuditLog.status == 'failed',
            AuditLog.created_at >= seven_days_ago
        ).order_by(desc(AuditLog.created_at)).limit(50).all()
        
        # Get age verification stats
        age_verifications = AuditLog.query.filter(
            AuditLog.action.in_(['age_verification', 'age_verification_denied']),
            AuditLog.created_at >= seven_days_ago
        ).all()
        
        # Get admin access logs
        admin_access = AuditLog.query.filter(
            AuditLog.action.in_(['admin_access', 'admin_access_denied']),
            AuditLog.created_at >= seven_days_ago
        ).order_by(desc(AuditLog.created_at)).limit(30).all()
        
        # Calculate statistics
        stats = {
            'suspicious_requests': len([log for log in suspicious_logs if log.action == 'suspicious_request']),
            'rate_limit_violations': len([log for log in suspicious_logs if log.action == 'rate_limit_exceeded']),
            'failed_logins': len(failed_logins),
            'age_verifications_success': len([log for log in age_verifications if log.action == 'age_verification']),
            'age_verifications_denied': len([log for log in age_verifications if log.action == 'age_verification_denied']),
            'admin_access_attempts': len(admin_access)
        }
        
        return render_template('admin/security.html',
                             suspicious_logs=suspicious_logs,
                             failed_logins=failed_logins,
                             age_verifications=age_verifications,
                             admin_access=admin_access,
                             stats=stats)
    
    except Exception as e:
        current_app.logger.error(f"Security monitoring error: {str(e)}")
        return render_template('errors/500.html'), 500

@admin_bp.route('/api/security-stats')
@login_required
@admin_required
def api_security_stats():
    """API endpoint for security statistics"""
    try:
        # Get security stats for different time periods
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        stats = {}
        
        # Get stats for each time period
        for period, start_time in [('24h', last_24h), ('7d', last_7d), ('30d', last_30d)]:
            stats[period] = {
                'suspicious_requests': AuditLog.query.filter(
                    AuditLog.action == 'suspicious_request',
                    AuditLog.created_at >= start_time
                ).count(),
                'rate_limit_violations': AuditLog.query.filter(
                    AuditLog.action == 'rate_limit_exceeded',
                    AuditLog.created_at >= start_time
                ).count(),
                'failed_logins': AuditLog.query.filter(
                    AuditLog.action == 'user_login',
                    AuditLog.status == 'failed',
                    AuditLog.created_at >= start_time
                ).count(),
                'age_verifications': AuditLog.query.filter(
                    AuditLog.action == 'age_verification',
                    AuditLog.created_at >= start_time
                ).count(),
                'age_verification_denials': AuditLog.query.filter(
                    AuditLog.action == 'age_verification_denied',
                    AuditLog.created_at >= start_time
                ).count()
            }
        
        # Get top suspicious IPs
        suspicious_ips = db.session.query(
            AuditLog.ip_address,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.action.in_(['suspicious_request', 'rate_limit_exceeded']),
            AuditLog.created_at >= last_7d
        ).group_by(AuditLog.ip_address).order_by(desc('count')).limit(10).all()
        
        stats['top_suspicious_ips'] = [{'ip': ip, 'count': count} for ip, count in suspicious_ips]
        
        return jsonify(stats)
    
    except Exception as e:
        current_app.logger.error(f"Security stats API error: {str(e)}")
        return jsonify({'error': 'Failed to fetch security statistics'}), 500