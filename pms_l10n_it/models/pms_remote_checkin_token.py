# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import uuid
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PmsRemoteCheckinToken(models.Model):
    _name = "pms.remote.checkin.token"
    _description = "Remote Check-in Token"
    _order = "create_date desc"

    name = fields.Char(
        string="Token",
        required=True,
        index=True,
        default=lambda self: str(uuid.uuid4())
    )
    
    reservation_id = fields.Many2one(
        "pms.reservation",
        string="Reservation",
        required=True,
        ondelete="cascade"
    )
    
    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        related="reservation_id.pms_property_id",
        store=True
    )
    
    guest_email = fields.Char(
        string="Guest Email",
        required=True
    )
    
    expires_at = fields.Datetime(
        string="Expires At",
        required=True,
        default=lambda self: fields.Datetime.now() + timedelta(days=7)
    )
    
    state = fields.Selection([
        ('sent', 'Sent'),
        ('accessed', 'Accessed'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    ], string="Status", default='sent', required=True)
    
    access_count = fields.Integer(
        string="Access Count",
        default=0
    )
    
    last_access = fields.Datetime(
        string="Last Access"
    )
    
    completed_date = fields.Datetime(
        string="Completed Date"
    )
    
    # Reminder functionality fields
    reminder_sent = fields.Boolean(
        string="Reminder Sent",
        default=False,
        help="Indicates if a reminder email has been sent"
    )
    
    reminder_sent_date = fields.Datetime(
        string="Reminder Sent Date",
        help="Date and time when the reminder was sent"
    )
    
    checkin_data_ids = fields.One2many(
        "pms.remote.checkin.data",
        "token_id",
        string="Check-in Data"
    )

    checkin_url = fields.Char(
        string="Check-in URL",
        compute="_compute_checkin_url"
    )

    @api.depends('name')
    def _compute_checkin_url(self):
        for record in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            record.checkin_url = f"{base_url}/remote-checkin/{record.name}"
    
    @api.model
    def generate_token_for_reservation(self, reservation_id, guest_email):
        """Generate a new remote check-in token for a reservation"""
        reservation = self.env['pms.reservation'].browse(reservation_id)
        
        if not reservation.exists():
            raise UserError(_("Reservation not found"))
        
        # Check if property has remote check-in enabled
        if not reservation.pms_property_id.remote_checkin_enabled:
            raise UserError(_("Remote check-in not available for this property"))
        
        # Invalidate existing tokens for this reservation
        existing_tokens = self.search([
            ('reservation_id', '=', reservation_id),
            ('state', 'in', ['sent', 'accessed'])
        ])
        existing_tokens.write({'state': 'expired'})
        
        # Create new token
        token = self.create({
            'reservation_id': reservation_id,
            'guest_email': guest_email,
        })
        
        # Send email with link
        token._send_checkin_email()
        
        return token
    
    def _send_checkin_email(self):
        """Send check-in email to guest"""
        self.ensure_one()
        
        template = self.env.ref(
            'pms_l10n_it.email_template_remote_checkin', 
            raise_if_not_found=False
        )
        
        if template:
            try:
                template.send_mail(self.id)
                self.state = 'sent'
                _logger.info("Remote check-in email sent for token %s to %s", self.name, self.guest_email)
            except Exception as e:
                _logger.error("Failed to send check-in email for token %s: %s", self.name, str(e))
                raise UserError(_("Failed to send check-in email: %s") % str(e))
        else:
            _logger.warning("Remote check-in email template not found")
            raise UserError(_("Remote check-in email template not configured"))
    
    def _send_reminder_email(self):
        """Send a reminder email to the guest for remote check-in"""
        self.ensure_one()
        
        # Check if token is still valid
        if self.state not in ['sent', 'accessed']:
            _logger.warning("Cannot send reminder for token %s in state %s", self.name, self.state)
            return False
        
        if self.expires_at < fields.Datetime.now():
            self.state = 'expired'
            _logger.warning("Cannot send reminder for expired token %s", self.name)
            return False
        
        # Check if reminder was already sent
        if self.reminder_sent:
            _logger.info("Reminder already sent for token %s", self.name)
            return True
        
        template = self.env.ref(
            'pms_l10n_it.email_template_remote_checkin_reminder', 
            raise_if_not_found=False
        )
        
        if template:
            try:
                template.send_mail(self.id, force_send=True)
                
                # Mark reminder as sent
                self.write({
                    'reminder_sent': True,
                    'reminder_sent_date': fields.Datetime.now()
                })
                
                _logger.info("Reminder email sent for token %s to %s", self.name, self.guest_email)
                return True
                
            except Exception as e:
                _logger.error("Failed to send reminder email for token %s: %s", self.name, str(e))
                return False
        else:
            _logger.warning("Reminder email template not found")
            return False

    def get_checkin_url(self):
        """Get the check-in URL for this token"""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/remote-checkin/{self.name}"
    
    def validate_token_access(self):
        """Validate token for access"""
        self.ensure_one()
        
        if self.state == 'expired':
            raise UserError(_("This check-in link has expired"))
        
        if self.expires_at < fields.Datetime.now():
            self.state = 'expired'
            raise UserError(_("This check-in link has expired"))
        
        # Update access tracking
        self.write({
            'access_count': self.access_count + 1,
            'last_access': fields.Datetime.now(),
            'state': 'accessed' if self.state == 'sent' else self.state
        })
        
        return True
    
    def complete_checkin(self):
        """Mark check-in as completed"""
        self.ensure_one()
        
        if self.state != 'accessed':
            raise UserError(_("Invalid token state for completion"))
        
        # Validate that all required data is provided
        if not self.checkin_data_ids:
            raise UserError(_("No check-in data provided"))
        
        # Transfer data to actual checkin partners
        self._transfer_to_checkin_partners()
        
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now()
        })
        
        _logger.info("Remote check-in completed for token %s", self.name)
    
    def _transfer_to_checkin_partners(self):
        """Transfer remote check-in data to actual checkin partners"""
        self.ensure_one()
        
        for data in self.checkin_data_ids:
            # Find or create checkin partner
            checkin_partner = self.env['pms.checkin.partner'].search([
                ('reservation_id', '=', self.reservation_id.id),
                ('firstname', '=', data.firstname),
                ('lastname', '=', data.lastname),
            ], limit=1)
            
            if not checkin_partner:
                checkin_partner = self.env['pms.checkin.partner'].create({
                    'reservation_id': self.reservation_id.id,
                    'firstname': data.firstname,
                    'lastname': data.lastname,
                })
            
            # Update with remote check-in data
            checkin_partner.write({
                'birthdate_date': data.birthdate_date,
                'nationality_id': data.nationality_id.id if data.nationality_id else False,
                'residence_country_id': data.residence_country_id.id if data.residence_country_id else False,
                'residence_state_id': data.residence_state_id.id if data.residence_state_id else False,
                'residence_city_id': data.residence_city_id.id if data.residence_city_id else False,
                'document_type': data.document_type,
                'document_number': data.document_number,
                'document_expedition_date': data.document_expedition_date,
                'gender': data.gender,
                'email': data.email,
                'phone': data.phone,
                'arrival': data.arrival or self.reservation_id.checkin,
                'departure': data.departure or self.reservation_id.checkout,
                'state': 'precheckin',  # Mark as pre-checked-in
            })
            
            _logger.info("Transferred remote check-in data for guest %s %s", 
                        data.firstname, data.lastname)

    def action_resend_email(self):
        """Resend the check-in email"""
        self.ensure_one()
        
        if self.state == 'expired':
            raise UserError(_("Cannot resend email for expired token"))
        
        self._send_checkin_email()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Email Resent'),
                'message': _('Check-in email has been resent to %s') % self.guest_email,
                'type': 'success',
            }
        }
    
    def action_send_reminder(self):
        """Send reminder email manually"""
        self.ensure_one()
        
        if self._send_reminder_email():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reminder Sent'),
                    'message': _('Reminder email has been sent to %s') % self.guest_email,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Reminder Failed'),
                    'message': _('Failed to send reminder email to %s') % self.guest_email,
                    'type': 'danger',
                }
            }
    
    def action_expire_token(self):
        """Manually expire the token"""
        self.ensure_one()
        
        self.state = 'expired'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Token Expired'),
                'message': _('Check-in token has been expired'),
                'type': 'info',
            }
        }


class PmsRemoteCheckinData(models.Model):
    _name = "pms.remote.checkin.data"
    _description = "Remote Check-in Guest Data"
    _order = "create_date"

    token_id = fields.Many2one(
        "pms.remote.checkin.token",
        string="Token",
        required=True,
        ondelete="cascade"
    )
    
    # Guest personal information
    firstname = fields.Char(
        string="First Name",
        required=True
    )
    
    lastname = fields.Char(
        string="Last Name",
        required=True
    )
    
    birthdate_date = fields.Date(
        string="Birth Date",
        required=True
    )
    
    gender = fields.Selection([
        ('M', 'Male'),
        ('F', 'Female'),
    ], string="Gender", required=True)
    
    nationality_id = fields.Many2one(
        "res.country",
        string="Nationality",
        required=True
    )
    
    # Residence information
    residence_country_id = fields.Many2one(
        "res.country",
        string="Country of Residence",
        required=True
    )
    
    residence_state_id = fields.Many2one(
        "res.country.state",
        string="State of Residence"
    )
    
    residence_city_id = fields.Many2one(
        "res.city",
        string="City of Residence"
    )
    
    # Document information
    document_type = fields.Selection([
        ('passport', 'Passport'),
        ('id_card', 'ID Card'),
        ('driving_license', 'Driving License'),
        ('other', 'Other'),
    ], string="Document Type", required=True)
    
    document_number = fields.Char(
        string="Document Number",
        required=True
    )
    
    document_expedition_date = fields.Date(
        string="Document Issue Date",
        required=True
    )
    
    document_expiry_date = fields.Date(
        string="Document Expiry Date"
    )
    
    # Contact information
    email = fields.Char(
        string="Email"
    )
    
    phone = fields.Char(
        string="Phone"
    )
    
    # Stay information
    arrival = fields.Date(
        string="Arrival Date"
    )
    
    departure = fields.Date(
        string="Departure Date"
    )
    
    # Privacy and consent
    privacy_consent = fields.Boolean(
        string="Privacy Consent",
        required=True,
        help="Guest has consented to data processing"
    )
    
    marketing_consent = fields.Boolean(
        string="Marketing Consent",
        help="Guest has consented to marketing communications"
    )
    
    # Additional fields for Italian registration
    place_of_birth = fields.Char(
        string="Place of Birth",
        help="City or place where the guest was born"
    )
    
    document_issue_place = fields.Char(
        string="Document Issue Place",
        help="Place where the document was issued"
    )
    
    # Data validation
    @api.constrains('birthdate_date')
    def _check_birthdate(self):
        for record in self:
            if record.birthdate_date and record.birthdate_date > fields.Date.today():
                raise ValidationError(_("Birth date cannot be in the future"))
            
            # Check minimum age (usually 0, but some countries have restrictions)
            if record.birthdate_date:
                age = (fields.Date.today() - record.birthdate_date).days / 365.25
                if age > 150:  # Reasonable maximum age
                    raise ValidationError(_("Birth date seems unrealistic"))
    
    @api.constrains('document_expedition_date', 'document_expiry_date')
    def _check_document_dates(self):
        for record in self:
            if record.document_expedition_date and record.document_expedition_date > fields.Date.today():
                raise ValidationError(_("Document issue date cannot be in the future"))
            
            if (record.document_expedition_date and record.document_expiry_date and 
                record.document_expiry_date <= record.document_expedition_date):
                raise ValidationError(_("Document expiry date must be after issue date"))
            
            # Check if document is expired
            if record.document_expiry_date and record.document_expiry_date < fields.Date.today():
                raise ValidationError(_("Document has expired"))
    
    @api.constrains('arrival', 'departure')
    def _check_stay_dates(self):
        for record in self:
            if record.arrival and record.departure and record.departure <= record.arrival:
                raise ValidationError(_("Departure date must be after arrival date"))
            
            if record.arrival and record.arrival < fields.Date.today():
                # Allow past arrival dates for flexibility, but log a warning
                _logger.warning("Guest %s %s has arrival date in the past: %s", 
                              record.firstname, record.lastname, record.arrival)
    
    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email:
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, record.email):
                    raise ValidationError(_("Invalid email format"))
    
    @api.model
    def create(self, vals_list):
        """Override create to log guest data creation"""
        result = super().create(vals_list)
        _logger.info("Remote check-in data created for guest %s %s", 
                    result.firstname, result.lastname)
        return result