# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from pytz import timezone
import logging

_logger = logging.getLogger(__name__)


class PmsGuestRegistrationWizard(models.TransientModel):
    _name = "pms.guest.registration.wizard"
    _description = "Italian Guest Registration Wizard"

    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        required=True,
        default=lambda self: self._default_property_id()
    )
    
    registration_date = fields.Date(
        string="Registration Date",
        required=True,
        default=fields.Date.today
    )
    
    checkin_partner_ids = fields.Many2many(
        "pms.checkin.partner",
        string="Guests to Register",
        default=lambda self: self._default_checkin_partner_ids()
    )
    
    all_unregistered_guests = fields.Many2many(
        "pms.checkin.partner",
        relation="wizard_all_guests_rel",
        string="All Unregistered Guests",
        compute="_compute_all_unregistered_guests",
        readonly=True
    )
    
    guest_count = fields.Integer(
        string="Selected Guests",
        compute="_compute_guest_count",
        store=True
    )
    
    show_registered_guests = fields.Boolean(
        string="Show Already Registered",
        default=False
    )
    
    notes = fields.Text(
        string="Notes"
    )
    
    auto_apply_exemptions = fields.Boolean(
        string="Auto-apply Exemptions",
        default=True,
        help="Automatically apply exemptions for minors and other cases"
    )
    
    filter_by_arrival = fields.Selection([
        ('today', "Today's Arrivals"),
        ('yesterday', "Yesterday's Arrivals"),
        ('week', 'Last 7 Days'),
        ('custom', 'Custom Date Range'),
        ('all', 'All Unregistered'),
    ], string="Filter by Arrival", default='today')
    
    date_from = fields.Date(
        string="From Date",
        default=fields.Date.today
    )
    
    date_to = fields.Date(
        string="To Date",
        default=fields.Date.today
    )

    @api.model
    def _default_property_id(self):
        """Get default property from context or user's default"""
        property_id = self.env.context.get('default_property_id')
        if property_id:
            return property_id
        # Try to get from user's default property if available
        return self.env.user.pms_property_ids[0] if self.env.user.pms_property_ids else False
    
    @api.model
    def _default_checkin_partner_ids(self):
        """Pre-select guests based on property configuration"""
        property_id = self._default_property_id()
        if not property_id:
            return False
            
        property_obj = self.env['pms.property'].browse(property_id)
        
        # Use property's auto-selection method
        if hasattr(property_obj, 'get_guests_for_auto_registration'):
            return property_obj.get_guests_for_auto_registration()
        
        # Fallback to basic selection
        return self.env['pms.checkin.partner'].search([
            ('pms_property_id', '=', property_id),
            ('state', '=', 'onboard'),
            ('it_registered', '=', False),
            ('arrival', '=', fields.Date.today()),
        ])
    
    @api.depends('filter_by_arrival', 'date_from', 'date_to', 'property_id', 'show_registered_guests')
    def _compute_all_unregistered_guests(self):
        for wizard in self:
            domain = [
                ('state', '=', 'onboard'),
            ]
            
            # Property filter
            if wizard.property_id:
                if 'pms_property_id' in self.env['pms.checkin.partner']._fields:
                    domain.append(('pms_property_id', '=', str(wizard.property_id.id)))
                elif 'property_id' in self.env['pms.checkin.partner']._fields:
                    domain.append(('property_id', '=', str(wizard.property_id.id)))
                else:
                    reservations = self.env['pms.reservation'].search([
                        ('pms_property_id', '=', str(wizard.property_id.id)),
                        ('state', 'in', ['onboard', 'confirm']),
                    ])
                    domain.append(('reservation_id', 'in', reservations.ids))
            
            # Registration status filter
            if not wizard.show_registered_guests:
                domain.append(('it_registered', '=', False))
            
            # Date filter based on selection
            user_tz = self.env.user.tz or 'UTC'
            user_timezone = timezone(user_tz)
            if wizard.filter_by_arrival == 'today':
                domain.extend([
                    ('arrival', '>=', fields.Date.today().isoformat()),
                    ('arrival', '<', (fields.Date.today() + timedelta(days=1)).isoformat())
                ])
            elif wizard.filter_by_arrival == 'yesterday':
                domain.extend([
                    ('arrival', '>=', (fields.Date.today() - timedelta(days=1)).isoformat()),
                    ('arrival', '<', fields.Date.today().isoformat())
                ])
            elif wizard.filter_by_arrival == 'week':
                domain.extend([
                    ('arrival', '>=', (fields.Date.today() - timedelta(days=7)).isoformat()),
                    ('arrival', '<=', fields.Date.today().isoformat())
                ])
            elif wizard.filter_by_arrival == 'custom':
                if wizard.date_from:
                    domain.append(('arrival', '>=', wizard.date_from.isoformat()))
                if wizard.date_to:
                    domain.append(('arrival', '<=', wizard.date_to.isoformat()))
            
            wizard.all_unregistered_guests = self.env['pms.checkin.partner'].search(domain)
    
    @api.depends('checkin_partner_ids')
    def _compute_guest_count(self):
        for wizard in self:
            wizard.guest_count = len(wizard.checkin_partner_ids)
    
    def action_select_all_guests(self):
        """Select all unregistered guests"""
        self.checkin_partner_ids = self.all_unregistered_guests
        return {'type': 'ir.actions.do_nothing'}
    
    def action_select_today_checkins(self):
        """Select only today's check-ins"""
        self.filter_by_arrival = 'today'
        self._compute_all_unregistered_guests()
        self.checkin_partner_ids = self.all_unregistered_guests.filtered(
            lambda g: not g.it_registered
        )
        return {'type': 'ir.actions.do_nothing'}
    
    def action_clear_selection(self):
        """Clear guest selection"""
        self.checkin_partner_ids = False
        return {'type': 'ir.actions.do_nothing'}
    
    def action_apply_auto_exemptions(self):
        """Apply automatic exemptions based on rules"""
        if not self.property_id:
            return
            
        for guest in self.checkin_partner_ids:
            # Check if minor
            if guest.birthdate_date:
                age = (fields.Date.today() - guest.birthdate_date).days / 365.25
                if age < self.property_id.exempt_minors_under_age:
                    guest.write({
                        'it_exemption_reason': 'minor',
                        'it_exemption_notes': _('Auto-exempted: Minor under %s years') % self.property_id.exempt_minors_under_age
                    })
                    self.checkin_partner_ids -= guest
        
        return {'type': 'ir.actions.do_nothing'}
    
    def action_register_guests(self):
        """Create registration and send to Alloggiati Web"""
        if not self.checkin_partner_ids:
            raise UserError(_("Please select at least one guest to register."))
        
        # Apply auto-exemptions if enabled
        if self.auto_apply_exemptions:
            self.action_apply_auto_exemptions()
        
        # Create registration record
        registration = self.env['pms.guest.registration'].create({
            'property_id': self.property_id.id,
            'registration_date': self.registration_date,
            'checkin_partner_ids': [(6, 0, self.checkin_partner_ids.ids)],
        })
        
        # Send registration
        registration.action_send_registration()
        
        # Show the created registration
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pms.guest.registration',
            'res_id': registration.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_create_draft_registration(self):
        """Create draft registration without sending"""
        if not self.checkin_partner_ids:
            raise UserError(_("Please select at least one guest to register."))
        
        registration = self.env['pms.guest.registration'].create({
            'property_id': self.property_id.id,
            'registration_date': self.registration_date,
            'checkin_partner_ids': [(6, 0, self.checkin_partner_ids.ids)],
            'state': 'draft',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pms.guest.registration',
            'res_id': registration.id,
            'view_mode': 'form',
            'target': 'current',
        }