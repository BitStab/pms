# Copyright 2024 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class PmsGuestRegistrationDashboard(models.Model):
    _name = "pms.guest.registration.dashboard"
    _description = "Guest Registration Dashboard"
    _auto = False
    _order = "property_id, date desc"

    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        readonly=True
    )
    
    date = fields.Date(
        string="Date",
        readonly=True
    )
    
    total_guests = fields.Integer(
        string="Total Guests",
        readonly=True
    )
    
    registered_guests = fields.Integer(
        string="Registered",
        readonly=True
    )
    
    pending_guests = fields.Integer(
        string="Pending",
        readonly=True
    )
    
    exempted_guests = fields.Integer(
        string="Exempted",
        readonly=True
    )
    
    failed_registrations = fields.Integer(
        string="Failed",
        readonly=True
    )
    
    registration_rate = fields.Float(
        string="Registration Rate %",
        readonly=True
    )

    def init(self):
        """Create or replace the SQL view for the dashboard"""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pms_guest_registration_dashboard AS (
                SELECT
                    row_number() OVER () AS id,
                    p.id AS property_id,
                    DATE(cp.arrival) AS date,
                    COUNT(DISTINCT cp.id) AS total_guests,
                    COUNT(DISTINCT CASE WHEN cp.it_registered = true THEN cp.id END) AS registered_guests,
                    COUNT(DISTINCT CASE WHEN cp.it_registered = false AND cp.it_exemption_reason IS NULL THEN cp.id END) AS pending_guests,
                    COUNT(DISTINCT CASE WHEN cp.it_exemption_reason IS NOT NULL THEN cp.id END) AS exempted_guests,
                    COUNT(DISTINCT CASE WHEN gr.state = 'error' THEN cp.id END) AS failed_registrations,
                    CASE 
                        WHEN COUNT(DISTINCT cp.id) > 0 
                        THEN (COUNT(DISTINCT CASE WHEN cp.it_registered = true THEN cp.id END)::float / COUNT(DISTINCT cp.id)::float) * 100
                        ELSE 0 
                    END AS registration_rate
                FROM pms_checkin_partner cp
                INNER JOIN pms_property p ON (
                    cp.property_id = p.id OR 
                    cp.pms_property_id = p.id OR
                    EXISTS (
                        SELECT 1 FROM pms_reservation r 
                        WHERE r.id = cp.reservation_id 
                        AND r.pms_property_id = p.id
                    )
                )
                LEFT JOIN pms_guest_registration_pms_checkin_partner_rel rel ON rel.pms_checkin_partner_id = cp.id
                LEFT JOIN pms_guest_registration gr ON gr.id = rel.pms_guest_registration_id
                WHERE cp.state = 'onboard'
                AND cp.arrival >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY p.id, DATE(cp.arrival)
            )
        """)

    @api.model
    def get_registration_summary(self, property_id=None, date_from=None, date_to=None):
        """Get registration summary for given filters"""
        domain = []
        
        if property_id:
            domain.append(('property_id', '=', property_id))
        
        if date_from:
            domain.append(('date', '>=', date_from))
        
        if date_to:
            domain.append(('date', '<=', date_to))
        
        records = self.search(domain)
        
        return {
            'total_guests': sum(records.mapped('total_guests')),
            'registered_guests': sum(records.mapped('registered_guests')),
            'pending_guests': sum(records.mapped('pending_guests')),
            'exempted_guests': sum(records.mapped('exempted_guests')),
            'failed_registrations': sum(records.mapped('failed_registrations')),
            'average_registration_rate': sum(records.mapped('registration_rate')) / len(records) if records else 0,
        }


class PmsGuestRegistrationAlert(models.Model):
    _name = "pms.guest.registration.alert"
    _description = "Guest Registration Alert"
    _order = "create_date desc"

    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        required=True
    )
    
    alert_type = fields.Selection([
        ('pending_high', 'High Pending Registrations'),
        ('failed', 'Failed Registration'),
        ('deadline', 'Registration Deadline Approaching'),
        ('connection', 'Connection Error'),
    ], string="Alert Type", required=True)
    
    severity = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ], string="Severity", default='warning')
    
    message = fields.Text(
        string="Message",
        required=True
    )
    
    guest_count = fields.Integer(
        string="Affected Guests"
    )
    
    resolved = fields.Boolean(
        string="Resolved",
        default=False
    )
    
    resolved_date = fields.Datetime(
        string="Resolved Date"
    )
    
    resolved_by = fields.Many2one(
        'res.users',
        string="Resolved By"
    )

    @api.model
    def check_and_create_alerts(self):
        """Check for conditions that require alerts"""
        properties = self.env['pms.property'].search([
            ('it_guest_registration_enabled', '=', True)
        ])
        
        for property_rec in properties:
            # Check for high pending registrations
            pending_guests = self.env['pms.checkin.partner'].search_count([
                ('pms_property_id', '=', property_rec.id),
                ('state', '=', 'onboard'),
                ('it_registered', '=', False),
                ('it_exemption_reason', '=', False),
                ('arrival', '<=', fields.Date.today()),
            ])
            
            if pending_guests > 10:  # Threshold configurable
                existing_alert = self.search([
                    ('property_id', '=', property_rec.id),
                    ('alert_type', '=', 'pending_high'),
                    ('resolved', '=', False),
                    ('create_date', '>=', fields.Datetime.now() - timedelta(hours=24))
                ])
                
                if not existing_alert:
                    self.create({
                        'property_id': property_rec.id,
                        'alert_type': 'pending_high',
                        'severity': 'warning',
                        'message': _('%d guests are pending registration') % pending_guests,
                        'guest_count': pending_guests,
                    })
            
            # Check for approaching deadline (e.g., same day registration required)
            today_arrivals = self.env['pms.checkin.partner'].search_count([
                ('pms_property_id', '=', property_rec.id),
                ('state', '=', 'onboard'),
                ('it_registered', '=', False),
                ('it_exemption_reason', '=', False),
                ('arrival', '=', fields.Date.today()),
            ])
            
            if today_arrivals > 0 and datetime.now().hour >= 20:  # After 8 PM
                existing_alert = self.search([
                    ('property_id', '=', property_rec.id),
                    ('alert_type', '=', 'deadline'),
                    ('resolved', '=', False),
                    ('create_date', '>=', fields.Datetime.now() - timedelta(hours=4))
                ])
                
                if not existing_alert:
                    self.create({
                        'property_id': property_rec.id,
                        'alert_type': 'deadline',
                        'severity': 'error',
                        'message': _('%d guests arrived today still need registration') % today_arrivals,
                        'guest_count': today_arrivals,
                    })

    def action_resolve(self):
        """Mark alert as resolved"""
        self.write({
            'resolved': True,
            'resolved_date': fields.Datetime.now(),
            'resolved_by': self.env.user.id,
        })