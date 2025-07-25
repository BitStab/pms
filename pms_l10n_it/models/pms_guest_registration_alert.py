# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class PmsGuestRegistrationAlert(models.Model):
    _name = "pms.guest.registration.alert"
    _description = "Guest Registration Alert"
    _order = "create_date desc"
    
    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        required=True,
        ondelete="cascade"
    )
    
    alert_type = fields.Selection([
        ('pending_high', 'High Pending Registrations'),
        ('pending_low', 'Low Pending Registrations'),
        ('failed', 'Failed Registration'),
        ('deadline', 'Registration Deadline'),
        ('error', 'System Error'),
    ], string="Alert Type", required=True)
    
    severity = fields.Selection([
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ], string="Severity", required=True, default='warning')
    
    message = fields.Text(
        string="Message",
        required=True
    )
    
    guest_count = fields.Integer(
        string="Guest Count",
        default=0
    )
    
    resolved = fields.Boolean(
        string="Resolved",
        default=False
    )
    
    resolved_date = fields.Datetime(
        string="Resolved Date"
    )
    
    @api.model
    def check_and_create_alerts(self):
        """Cron method to check and create alerts"""
        properties = self.env['pms.property'].search([
            ('it_guest_registration_enabled', '=', True)
        ])
        
        for property_obj in properties:
            # Check pending registrations
            pending_guests = self.env['pms.checkin.partner'].search_count([
                ('pms_property_id', '=', property_obj.id),
                ('state', '=', 'onboard'),
                ('it_registered', '=', False),
                ('it_exemption_reason', '=', False),
            ])
            
            if pending_guests > 10:  # Threshold
                self._create_or_update_alert(
                    property_obj,
                    'pending_high',
                    'warning',
                    _('%d guests are pending registration') % pending_guests,
                    pending_guests
                )
            
        return True
    
    def _create_or_update_alert(self, property_obj, alert_type, severity, message, guest_count=0):
        """Create or update an alert"""
        # Check if similar unresolved alert exists
        existing = self.search([
            ('property_id', '=', property_obj.id),
            ('alert_type', '=', alert_type),
            ('resolved', '=', False),
        ], limit=1)
        
        if existing:
            existing.write({
                'message': message,
                'guest_count': guest_count,
                'severity': severity,
            })
        else:
            self.create({
                'property_id': property_obj.id,
                'alert_type': alert_type,
                'severity': severity,
                'message': message,
                'guest_count': guest_count,
            })