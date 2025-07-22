# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import secrets
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PmsRemoteCheckinToken(models.Model):
    _name = "pms.remote.checkin.token"
    _description = "Remote Check-in Token"
    _order = "create_date desc"
    _rec_name = "name"
    
    # Token Fields
    name = fields.Char(
        string="Token",
        required=True,
        copy=False,
        default=lambda self: self._generate_token(),
        readonly=True
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
        store=True,
        readonly=True
    )
    
    folio_id = fields.Many2one(
        "pms.folio",
        string="Folio",
        related="reservation_id.folio_id",
        store=True,
        readonly=True
    )
    
    # Main Guest Info
    guest_email = fields.Char(
        string="Main Guest Email",
        required=True
    )
    
    guest_name = fields.Char(
        string="Main Guest Name",
        required=True
    )
    
    # Token Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accessed', 'Accessed'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='draft', tracking=True)
    
    # Dates
    sent_date = fields.Datetime(
        string="Sent Date",
        readonly=True
    )
    
    accessed_date = fields.Datetime(
        string="First Access Date",
        readonly=True
    )
    
    completed_date = fields.Datetime(
        string="Completed Date",
        readonly=True
    )
    
    expires_at = fields.Datetime(
        string="Expires At",
        required=True,
        default=lambda self: fields.Datetime.now() + timedelta(days=7)
    )
    
    # Check-in Data
    checkin_data_ids = fields.One2many(
        "pms.remote.checkin.data",
        "token_id",
        string="Check-in Data"
    )
    
    # Guest Invitations
    guest_invitation_ids = fields.One2many(
        "pms.guest.invitation",
        "token_id",
        string="Guest Invitations"
    )
    
    # Statistics
    access_count = fields.Integer(
        string="Access Count",
        default=0,
        readonly=True
    )
    
    completed_guests = fields.Integer(
        string="Completed Guests",
        compute="_compute_completed_guests"
    )
    
    total_guests = fields.Integer(
        string="Total Guests",
        compute="_compute_total_guests"
    )
    
    completion_rate = fields.Float(
        string="Completion Rate (%)",
        compute="_compute_completion_rate"
    )
    
    # Configuration
    language = fields.Selection(
        string="Language",
        selection="_get_language_selection",
        default=lambda self: self.env.lang
    )
    
    reminder_sent = fields.Boolean(
        string="Reminder Sent",
        default=False
    )
    
    @api.model
    def _generate_token(self):
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)
    
    @api.model
    def _get_language_selection(self):
        """Get available languages"""
        return self.env['res.lang'].get_installed()
    
    @api.depends('checkin_data_ids', 'guest_invitation_ids')
    def _compute_completed_guests(self):
        """Count completed check-ins"""
        for token in self:
            completed_data = token.checkin_data_ids.filtered('is_complete')
            completed_invitations = token.guest_invitation_ids.filtered(
                lambda i: i.state == 'completed'
            )
            token.completed_guests = len(completed_data) + len(completed_invitations)
    
    @api.depends('reservation_id.checkin_partner_ids')
    def _compute_total_guests(self):
        """Count total expected guests"""
        for token in self:
            token.total_guests = len(token.reservation_id.checkin_partner_ids)
    
    @api.depends('completed_guests', 'total_guests')
    def _compute_completion_rate(self):
        """Calculate completion percentage"""
        for token in self:
            if token.total_guests > 0:
                token.completion_rate = (token.completed_guests / token.total_guests) * 100
            else:
                token.completion_rate = 0.0
    
    def action_send_token(self):
        """Send the check-in link to main guest"""
        self.ensure_one()
        
        if self.state not in ['draft', 'sent']:
            raise UserError(_("Token has already been used or expired"))
        
        # Send email
        template = self.env.ref('pms_l10n_it.email_template_remote_checkin', False)
        if template:
            template.with_context(lang=self.language).send_mail([self.id], force_send=True)
        
        self.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Check-in Link Sent'),
                'message': _('Check-in link has been sent to %s') % self.guest_email,
                'type': 'success',
            }
        }
    
    def action_send_reminder(self):
        """Send reminder email"""
        self.ensure_one()
        
        if self.state != 'sent':
            raise UserError(_("Can only send reminders for sent tokens"))
        
        if self.reminder_sent:
            raise UserError(_("Reminder has already been sent"))
        
        # Send reminder email
        template = self.env.ref('pms_l10n_it.email_template_remote_checkin_reminder', False)
        if template:
            template.with_context(lang=self.language).send_mail(self.id, force_send=True)
        
        self.reminder_sent = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reminder Sent'),
                'message': _('Reminder has been sent to %s') % self.guest_email,
                'type': 'success',
            }
        }
    
    def action_send_guest_invitations(self, guest_emails):
        """Send check-in invitations to additional guests"""
        self.ensure_one()
        
        if not guest_emails:
            raise UserError(_("No guest emails provided"))
        
        created_invitations = self.env['pms.guest.invitation']
        
        for email in guest_emails:
            # Skip if invitation already exists
            existing = self.guest_invitation_ids.filtered(
                lambda i: i.guest_email == email
            )
            if existing:
                continue
            
            # Create invitation
            invitation = self.env['pms.guest.invitation'].create({
                'token_id': self.id,
                'guest_email': email,
                'guest_token': self._generate_token(),
                'language': self.language,
            })
            
            # Send invitation email
            invitation.action_send_invitation()
            created_invitations |= invitation
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invitations Sent'),
                'message': _('%d invitations sent successfully') % len(created_invitations),
                'type': 'success',
            }
        }
    
    def action_mark_accessed(self):
        """Mark token as accessed"""
        self.ensure_one()
        
        if self.state == 'sent':
            self.write({
                'state': 'accessed',
                'accessed_date': fields.Datetime.now(),
                'access_count': self.access_count + 1
            })
        else:
            self.access_count += 1
    
    def action_complete_checkin(self):
        """Mark check-in as completed"""
        self.ensure_one()
        
        if self.state in ['sent', 'accessed']:
            # Validate all required data is complete
            if not self._validate_completion():
                raise UserError(_("Not all required guest data has been provided"))
            
            # Transfer data to checkin partners
            self._transfer_to_checkin_partners()
            
            self.write({
                'state': 'completed',
                'completed_date': fields.Datetime.now()
            })
            
            # Create guest groups if applicable
            self._create_guest_groups()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Check-in Completed'),
                    'message': _('All guest data has been successfully collected'),
                    'type': 'success',
                }
            }

    def validate_token_access(self):
        """Validate token access and mark as accessed"""
        self.ensure_one()
        
        if self.state not in ['draft', 'sent']:
            raise UserError(_("Token has already been used or expired"))
        
        # Mark as accessed
        self.action_mark_accessed()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Token Accessed'),
                'message': _('You have successfully accessed the check-in link'),
                'type': 'success',
            }
        }   
    
    def _validate_completion(self):
        """Validate that all required data is complete"""
        self.ensure_one()
        
        # Check main guest data
        if not self.checkin_data_ids:
            return False
        
        main_guest_data = self.checkin_data_ids.filtered('is_main_guest')
        if not main_guest_data or not main_guest_data[0].is_complete:
            return False
        
        # Check all invited guests have completed
        pending_invitations = self.guest_invitation_ids.filtered(
            lambda i: i.state not in ['completed', 'cancelled']
        )
        if pending_invitations:
            return False
        
        return True
    
    def _transfer_to_checkin_partners(self):
        """Transfer collected data to pms.checkin.partner records"""
        self.ensure_one()
        
        # Transfer main guest data
        for data in self.checkin_data_ids:
            checkin_partner = self._find_or_create_checkin_partner(data)
            data._transfer_to_checkin_partner(checkin_partner)
        
        # Transfer invitation data
        for invitation in self.guest_invitation_ids.filtered(lambda i: i.state == 'completed'):
            if invitation.checkin_data_id:
                checkin_partner = self._find_or_create_checkin_partner(invitation.checkin_data_id)
                invitation.checkin_data_id._transfer_to_checkin_partner(checkin_partner)
    
    def _find_or_create_checkin_partner(self, checkin_data):
        """Find existing or create new checkin partner"""
        # Try to find by name and reservation
        existing = self.env['pms.checkin.partner'].search([
            ('reservation_id', '=', self.reservation_id.id),
            ('firstname', '=', checkin_data.firstname),
            ('lastname', '=', checkin_data.lastname),
        ], limit=1)
        
        if existing:
            return existing
        
        # Create new
        return self.env['pms.checkin.partner'].create({
            'reservation_id': self.reservation_id.id,
            'firstname': checkin_data.firstname,
            'lastname': checkin_data.lastname,
            'email': checkin_data.email,
            'self_checkin_completed': True,
        })
    
    def _create_guest_groups(self):
        """Create guest groups after check-in completion"""
        self.ensure_one()
        
        # Check if group creation is needed
        if len(self.reservation_id.checkin_partner_ids) >= 2:
            # Check if group already exists
            existing_group = self.env['pms.guest.group'].search([
                ('reservation_id', '=', self.reservation_id.id)
            ], limit=1)
            
            if not existing_group:
                # Auto-create group
                groups = self.env['pms.guest.group'].auto_create_groups(
                    reservation_ids=[self.reservation_id.id]
                )
                if groups:
                    _logger.info("Auto-created guest group for reservation %s", 
                                self.reservation_id.name)
    
    def get_checkin_url(self):
        """Get the self check-in URL"""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/checkin/{self.name}"
    
    @api.model
    def _cron_check_expired_tokens(self):
        """Cron job to mark expired tokens"""
        expired_tokens = self.search([
            ('state', 'in', ['draft', 'sent', 'accessed']),
            ('expires_at', '<', fields.Datetime.now())
        ])
        
        expired_tokens.write({'state': 'expired'})
        _logger.info("Marked %d tokens as expired", len(expired_tokens))
    
    @api.model
    def _cron_send_reminders(self):
        """Cron job to send check-in reminders"""
        # Get properties with reminder settings
        properties = self.env['pms.property'].search([
            ('remote_checkin_enabled', '=', True),
            ('remote_checkin_reminder_hours', '>', 0)
        ])
        
        for prop in properties:
            reminder_time = fields.Datetime.now() + timedelta(
                hours=prop.remote_checkin_reminder_hours
            )
            
            # Find tokens needing reminders
            tokens = self.search([
                ('property_id', '=', prop.id),
                ('state', '=', 'sent'),
                ('reminder_sent', '=', False),
                ('reservation_id.checkin', '<=', reminder_time),
                ('reservation_id.checkin', '>', fields.Datetime.now())
            ])
            
            for token in tokens:
                try:
                    token.action_send_reminder()
                except Exception as e:
                    _logger.error("Failed to send reminder for token %s: %s", 
                                 token.name, str(e))

    def complete_checkin(self):
        """
        Complete the remote check-in process by transferring collected data 
        from pms.remote.checkin.data to pms.checkin.partner records.
        Called by the controller after guest data has been collected.
        """
        self.ensure_one()
        
        if self.state not in ['sent', 'accessed']:
            raise UserError(_('This token has already been used or is invalid.'))
        
        if not self.checkin_data_ids:
            raise UserError(_('No check-in data found.'))
        
        if self.state == 'sent':
            self.action_mark_accessed()
        
        updated_partners = self.env['pms.checkin.partner']
        
        for checkin_data in self.checkin_data_ids:
            # Find matching checkin partner
            domain = [
                ('reservation_id', '=', self.reservation_id.id),
                ('firstname', 'ilike', checkin_data.firstname),
                ('lastname', 'ilike', checkin_data.lastname),
            ]
            
            checkin_partner = self.env['pms.checkin.partner'].search(domain, limit=1)
            
            if not checkin_partner:
                _logger.warning(
                    "No matching checkin partner found for %s %s",
                    checkin_data.firstname,
                    checkin_data.lastname
                )
                continue
            
            # Update checkin partner with collected data
            update_vals = {
                'birthdate_date': checkin_data.birthdate_date,
                'gender': checkin_data.gender,
                'email': checkin_data.email,
                'mobile': checkin_data.phone,
                'nationality_id': checkin_data.nationality_id.id if checkin_data.nationality_id else False,
                'document_type': checkin_data.document_type,
                'document_number': checkin_data.document_number,
                'document_expedition_date': checkin_data.document_expedition_date,
                'residence_country_id': checkin_data.residence_country_id.id if checkin_data.residence_country_id else False,
                'residence_state_id': checkin_data.residence_state_id.id if checkin_data.residence_state_id else False,
                'residence_city_id': checkin_data.residence_city_id.id if checkin_data.residence_city_id else False,
                'self_checkin_completed': True,
            }
            
            # Add Italian specific fields if they exist
            if hasattr(checkin_data, 'place_of_birth') and checkin_data.place_of_birth:
                update_vals['place_of_birth'] = checkin_data.place_of_birth
            
            if hasattr(checkin_data, 'document_issue_place') and checkin_data.document_issue_place:
                update_vals['document_issue_place'] = checkin_data.document_issue_place
            
            # Update state if we have enough data
            if update_vals.get('document_number') and update_vals.get('birthdate_date'):
                update_vals['state'] = 'onboard'
            
            checkin_partner.write(update_vals)
            updated_partners |= checkin_partner
        
        if not updated_partners:
            raise UserError(_('Could not match any check-in data with reservation guests.'))
        
        # Update token state
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now(),
            'completed_guests': len(updated_partners),
        })
        
        _logger.info(
            "Remote check-in completed for token %s - %d guests updated",
            self.name,
            len(updated_partners)
        )
        
        return True

class PmsGuestInvitation(models.Model):
    _name = "pms.guest.invitation"
    _description = "Guest Check-in Invitation"
    _order = "create_date desc"
    
    token_id = fields.Many2one(
        "pms.remote.checkin.token",
        string="Main Token",
        required=True,
        ondelete="cascade"
    )
    
    guest_email = fields.Char(
        string="Guest Email",
        required=True
    )
    
    guest_token = fields.Char(
        string="Guest Token",
        required=True,
        copy=False,
        readonly=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accessed', 'Accessed'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='draft', tracking=True)
    
    sent_date = fields.Datetime(
        string="Sent Date",
        readonly=True
    )
    
    accessed_date = fields.Datetime(
        string="Accessed Date",
        readonly=True
    )
    
    completed_date = fields.Datetime(
        string="Completed Date",
        readonly=True
    )
    
    checkin_data_id = fields.Many2one(
        "pms.remote.checkin.data",
        string="Check-in Data",
        readonly=True
    )
    
    language = fields.Selection(
        string="Language",
        selection="_get_language_selection",
        required=True
    )
    
    access_count = fields.Integer(
        string="Access Count",
        default=0,
        readonly=True
    )
    
    @api.model
    def _get_language_selection(self):
        """Get available languages"""
        return self.env['res.lang'].get_installed()
    
    def action_send_invitation(self):
        """Send invitation email to guest"""
        self.ensure_one()
        
        template = self.env.ref('pms_l10n_it.email_template_guest_invitation', False)
        if template:
            template.with_context(lang=self.language).send_mail(self.id, force_send=True)
        
        self.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now()
        })
    
    def get_checkin_url(self):
        """Get the guest-specific check-in URL"""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/checkin/guest/{self.guest_token}"

    