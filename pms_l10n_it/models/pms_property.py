# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class PmsProperty(models.Model):
    """Extension of PMS Property for Italian requirements"""
    _inherit = "pms.property"
    
    it_guest_registration_enabled = fields.Boolean(
        string="Italian Guest Registration Enabled",
        default=True,
        help="Enable italian guest registration for this property"
    )

    # Alloggiati Web Configuration
    alloggiati_web_user = fields.Char(
        string="Alloggiati Web User",
        help="Username for Alloggiati Web service"
    )
    alloggiati_web_password = fields.Char(
        string="Alloggiati Web Password",
        help="Password for Alloggiati Web service"
    )
    alloggiati_web_test_mode = fields.Boolean(
        string="Test Mode",
        default=True,
        help="Enable test mode for Alloggiati Web integration"
    )
    alloggiati_web_active = fields.Boolean(
        string="Alloggiati Web Active",
        default=False,
        help="Enable Alloggiati Web integration"
    )
    
    alloggiati_web_wskey = fields.Char(
        string="Alloggiati WS Key",
        help="Web Service Key for Alloggiati Web service"
    )

    # Italian Hotel Configuration
    it_hotel_code = fields.Char(
        string="Hotel Code",
        help="Official hotel code assigned by Italian authorities"
    )
    it_structure_type = fields.Selection([
        ('1', 'Albergo'),
        ('2', 'Villaggio Turistico'),
        ('3', 'Campeggio'),
        ('4', 'Alloggio Agrituristico'),
        ('5', 'Bed & Breakfast'),
        ('6', 'Residence'),
        ('7', 'Casa Vacanza'),
        ('8', 'Affittacamere'),
        ('9', 'Ostello'),
        ('10', 'Casa per Ferie'),
        ('11', 'Altro'),
    ], string="Categoria Struttura", help="Category of the accommodation structure")

    exempt_minors_under_age = fields.Integer(
        string="Exempt Minors Under Age",
        default=14,
        help="Age under which minors are exempt from registration"
    )
    
    # --- Automatic registration settings ---
    auto_register_checkin = fields.Boolean(
        string="Auto Register on Check-in",
        default=False,
        help="Automatically register guests when they check in"
    )
    auto_register_time = fields.Char(
        string="Auto Register Time",
        default="23:00",
        help="Time of day to automatically register guests (HH:MM format)"
    )
    
    registration_delay = fields.Integer(
        string="Registration Delay (hours)",
        default=3,
        help="Hours to wait after check-in before automatic registration"
    )
    
    # Automatic guest selection settings
    auto_select_guests = fields.Boolean(
        string="Auto-select Guests",
        default=True,
        help="Automatically select guests for registration based on criteria"
    )
    
    auto_select_criteria = fields.Selection([
        ('all', 'All Guests'),
        ('adults_only', 'Adults Only (18+)'),
        ('non_exempt', 'Non-exempt Only'),
        ('by_nationality', 'By Nationality'),
    ], string="Auto-selection Criteria",
        default='non_exempt',
        help="Criteria for automatic guest selection"
    )
    
    auto_select_nationalities = fields.Many2many(
        'res.country',
        string="Auto-select Nationalities",
        help="Nationalities to include in automatic selection (leave empty for all)"
    )

    # Guest Registration Statistics
    it_total_registrations = fields.Integer(
        string="Total Registrations",
        compute="_compute_registration_stats",
        store=True
    )
    it_pending_registrations = fields.Integer(
        string="Pending Registrations",
        compute="_compute_registration_stats",
        store=True
    )
    it_last_registration_date = fields.Date(
        string="Last Registration Date",
        compute="_compute_registration_stats",
        store=True
    )

    # Self-Check-In Configuration
    remote_checkin_enabled = fields.Boolean(
        string="Remote Check-in Enabled",
        default=False,
        help="Enable remote check-in for guests"
    )

    send_success_notifications = fields.Boolean(
        string="Send Success Notifications",
        default=False,
        help="Send weekly registration summary notifications"
    )

    registration_notification_emails = fields.Boolean(
        string="Registration Notification Emails",
        help="Enable registration notification emails"
    )

    remote_checkin_reminder_hours = fields.Integer(
        string="Remote Check-in Reminder Hours",
        default=72,
        help="Number of hours before check-in to send remote check-in reminder"
    )

    #@api.depends("id")
    def _compute_registration_stats(self):
        """Compute registration statistics"""
        for rec in self:
            registrations = self.env["pms.guest.registration"].search([
                ("property_id", "=", rec.id)
            ])
            
            rec.it_total_registrations = len(registrations)
            rec.it_pending_registrations = len(registrations.filtered(
                lambda r: r.state in ["draft", "validated"]
            ))
            
            if registrations:
                rec.it_last_registration_date = max(registrations.mapped("registration_date"))
            else:
                rec.it_last_registration_date = False
    
    def action_test_alloggiati_connection(self):
        """Test connection to Alloggiati Web service"""
        self.ensure_one()
        
        if not self.alloggiati_web_user or not self.alloggiati_web_password:
            raise ValidationError(_("Please configure Alloggiati Web credentials"))
        
        try:
            # Create a test registration to validate connection
            test_registration = self.env["pms.guest.registration"].new({
                "property_id": self.id,
                "alloggiati_user": self.alloggiati_web_user,
                "alloggiati_password": self.alloggiati_web_password,
                "test_mode": self.alloggiati_web_test_mode
            })
            
            token = test_registration._get_authentication_token()
            
            if token:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Connection Successful"),
                        "message": _("Successfully connected to Alloggiati Web service"),
                        "type": "success",
                    }
                }
            else:
                raise ValidationError(_("Failed to obtain authentication token"))
                
        except Exception as e:
            raise ValidationError(_("Connection failed: %s") % str(e))
    
    def action_view_guest_registrations(self):
        """View guest registrations for this property"""
        self.ensure_one()
        
        return {
            "type": "ir.actions.act_window",
            "name": _("Guest Registrations"),
            "res_model": "pms.guest.registration",
            "view_mode": "tree,form",
            "domain": [("property_id", "=", self.id)],
            "context": {
                "default_property_id": self.id,
                "search_default_group_by_state": 1,
            }
        }
    
    def action_view_pending_registrations(self):
        """View pending guest registrations"""
        self.ensure_one()
        
        return {
            "type": "ir.actions.act_window",
            "name": _("Pending Registrations"),
            "res_model": "pms.guest.registration",
            "view_mode": "tree,form",
            "domain": [
                ("property_id", "=", self.id),
                ("state", "in", ["draft", "validated"])
            ],
            "context": {
                "default_property_id": self.id,
            }
        }
    
    def action_view_registration_receipts(self):
        """View registration receipts for this property"""
        self.ensure_one()
        
        return {
            "type": "ir.actions.act_window",
            "name": _("Registration Receipts"),
            "res_model": "pms.guest.registration.receipt",
            "view_mode": "tree,form",
            "domain": [("property_id", "=", self.id)],
            "context": {
                "default_property_id": self.id,
                "search_default_this_month": 1,
            }
        }
    
    def action_sync_alloggiati_tables(self):
        """Synchronize reference tables from Alloggiati Web"""
        self.ensure_one()
        
        if not self.alloggiati_web_active:
            raise ValidationError(_("Alloggiati Web integration is not active"))
        
        # Create or get table manager
        table_manager = self.env["alloggiati.table.manager"].search([
            ("property_id", "=", self.id)
        ], limit=1)
        
        if not table_manager:
            table_manager = self.env["alloggiati.table.manager"].create({
                "property_id": self.id
            })
        
        return table_manager.action_sync_all_tables()
    
    def action_create_guest_registration(self):
        """Create guest registration wizard"""
        self.ensure_one()
        
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Guest Registration"),
            "res_model": "pms.guest.registration.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_property_id": self.id,
            }
        }
    
    @api.constrains("alloggiati_web_user", "alloggiati_web_password", "alloggiati_web_active")
    def _check_alloggiati_web_config(self):
        """Validate Alloggiati Web configuration"""
        for rec in self:
            if rec.alloggiati_web_active:
                if not rec.alloggiati_web_user:
                    raise ValidationError(_("Alloggiati Web user is required when integration is active"))
                if not rec.alloggiati_web_password:
                    raise ValidationError(_("Alloggiati Web password is required when integration is active"))
    
    def _get_italian_registration_settings(self):
        """Get Italian registration settings for this property"""
        self.ensure_one()
        
        return {
            "alloggiati_web_user": self.alloggiati_web_user,
            "alloggiati_web_password": self.alloggiati_web_password,
            "alloggiati_web_test_mode": self.alloggiati_web_test_mode,
            "alloggiati_web_active": self.alloggiati_web_active,
            "it_hotel_code": self.it_hotel_code,
            "it_structure_type": self.it_structure_type,
        }
    
    def get_guests_for_auto_registration(self):
        """
        Get guests that should be automatically registered based on property settings.
        
        This method is called from the guest registration wizard to pre-select
        guests based on the property's auto-selection configuration.
        
        Returns:
            recordset: pms.checkin.partner records to be registered
        """
        self.ensure_one()
        
        # Base domain for all queries
        domain = [
            ('state', '=', 'onboard'),
            ('it_registered', '=', False),
        ]
        
        # Add property filter
        if 'pms_property_id' in self.env['pms.checkin.partner']._fields:
            domain.append(('pms_property_id', '=', self.id))
        elif 'property_id' in self.env['pms.checkin.partner']._fields:
            domain.append(('property_id', '=', self.id))
        else:
            # Fallback: filter by reservations in this property
            reservations = self.env['pms.reservation'].search([
                ('pms_property_id', '=', self.id),
                ('state', 'in', ['onboard', 'confirm']),
            ])
            domain.append(('reservation_id', 'in', reservations.ids))
        
        # Apply auto-selection criteria if enabled
        if hasattr(self, 'auto_select_guests') and self.auto_select_guests:
            
            # Apply date filter based on registration delay
            if hasattr(self, 'registration_delay') and self.registration_delay > 0:
                # Only select guests who arrived at least X hours ago
                from datetime import datetime, timedelta
                cutoff_time = datetime.now() - timedelta(hours=self.registration_delay)
                domain.append(('arrival', '<=', cutoff_time.strftime('%Y-%m-%d %H:%M:%S')))
            else:
                # Default: today's arrivals
                domain.append(('arrival', '=', fields.Date.today()))
            
            # Apply selection criteria
            if hasattr(self, 'auto_select_criteria'):
                if self.auto_select_criteria == 'adults_only':
                    # Exclude minors (under 18)
                    domain.append('|')
                    domain.append(('birthdate_date', '=', False))
                    domain.append(('birthdate_date', '<=', fields.Date.today() - relativedelta(years=18)))
                    
                elif self.auto_select_criteria == 'non_exempt':
                    # Exclude already exempted guests
                    domain.extend([
                        '|',
                        ('it_exemption_reason', '=', False),
                        ('it_exemption_reason', '=', ''),
                    ])
                    
                elif self.auto_select_criteria == 'by_nationality':
                    # Filter by specific nationalities (requires configuration)
                    if hasattr(self, 'auto_select_nationalities') and self.auto_select_nationalities:
                        nationality_ids = self.auto_select_nationalities.ids
                        domain.append(('nationality_id', 'in', nationality_ids))
                        
                # For 'all' criteria or default, no additional filters needed
                
        else:
            # If auto-selection is not enabled, return today's unregistered arrivals
            domain.append(('arrival', '=', fields.Date.today()))
        
        # Additional filters to exclude certain guests
        if hasattr(self, 'exempt_minors_under_age') and self.exempt_minors_under_age > 0:
            # Optionally exclude minors under the exemption age
            # This is applied separately in the wizard's auto_apply_exemptions method
            pass
        
        # Search and return the filtered guests
        guests = self.env['pms.checkin.partner'].search(domain)
        
        # Log the selection for debugging
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(
            "Auto-registration selection for property %s: %d guests selected with criteria %s",
            self.name,
            len(guests),
            getattr(self, 'auto_select_criteria', 'default')
        )
        
        return guests

    @api.model
    def _cron_auto_guest_registration(self):
        """Cron job for automatic guest registration"""
        properties = self.search([
            ('it_guest_registration_enabled', '=', True),
            ('auto_register_checkin', '=', True),
        ])
        
        for prop in properties:
            try:
                # Get current time
                now = fields.Datetime.now()
                current_time = now.strftime('%H:%M')
                
                # Check if it's time to register
                if prop.auto_register_time == current_time:
                    guests = prop.get_guests_for_auto_registration()
                    
                    if guests:
                        # Create registration wizard
                        wizard = self.env['pms.guest.registration.wizard'].create({
                            'property_id': prop.id,
                            'registration_date': fields.Date.today(),
                            'checkin_partner_ids': [(6, 0, guests.ids)],
                            'auto_apply_exemptions': True,
                        })
                        
                        # Execute registration
                        wizard.action_register_guests()
                        
                        _logger.info(
                            "Auto-registration completed for property %s: %d guests",
                            prop.name,
                            len(guests)
                        )
            except Exception as e:
                _logger.error(
                    "Auto-registration failed for property %s: %s",
                    prop.name,
                    str(e)
                )
    
    @api.model
    def _cron_cleanup_old_data(self):
        """Cleanup old registration data"""
        # Cleanup old tokens
        old_date = fields.Datetime.now() - timedelta(days=365)
        old_tokens = self.env['pms.remote.checkin.token'].search([
            ('state', 'in', ['completed', 'expired', 'cancelled']),
            ('create_date', '<', old_date),
        ])
        old_tokens.unlink()
        
        _logger.info("Cleaned up %d old check-in tokens", len(old_tokens))
    
    def action_send_remote_checkin_links(self):
        """Send remote check-in links for upcoming reservations"""
        self.ensure_one()
        
        if not self.remote_checkin_enabled:
            return
        
        # Find eligible reservations
        tomorrow = fields.Date.today() + timedelta(days=1)
        eligible_date = tomorrow + timedelta(hours=self.remote_checkin_reminder_hours)
        
        reservations = self.env['pms.reservation'].search([
            ('pms_property_id', '=', self.id),
            ('state', 'in', ['confirm', 'onboard']),
            ('checkin', '>=', tomorrow),
            ('checkin', '<=', eligible_date),
        ])
        
        for reservation in reservations:
            # Check if token already exists
            existing_token = self.env['pms.remote.checkin.token'].search([
                ('reservation_id', '=', reservation.id),
                ('state', '!=', 'cancelled'),
            ], limit=1)
            
            if not existing_token and reservation.partner_id.email:
                # Create and send token
                token = self.env['pms.remote.checkin.token'].create({
                    'reservation_id': reservation.id,
                    'guest_email': reservation.partner_id.email,
                    'guest_name': reservation.partner_id.name,
                })
                token.action_send_token()

    # Find properties with remote check-in enabled
    def cron_generate_remote_checkin_links(self):
        """Cron job to generate remote check-in links for properties"""
        model = self.env['pms.property']
        
        # Search for properties with remote check-in enabled
        properties = model.search([('remote_checkin_enabled', '=', True)])

        for property_rec in properties:
            try:
                property_rec.action_send_remote_checkin_links()
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error("Error generating remote check-in links for property %s: %s", property_rec.name, str(e))
    
    # Send weekly summary for properties with notifications enabled
    def cron_send_weekly_registration_summary(self):
        """Cron job to send weekly registration summary for properties"""
        model = self.env['pms.property']
        

        properties = model.search([
            ('it_guest_registration_enabled', '=', True),
            ('send_success_notifications', '=', True),
            ('registration_notification_emails', '!=', False)
        ])

        for property_rec in properties:
            try:
                # Calculate weekly stats
                week_start = datetime.now() - timedelta(days=7)
                registrations = self.env['pms.guest.registration'].search([
                    ('property_id', '=', property_rec.id),
                    ('create_date', '>=', week_start),
                    ('state', '=', 'sent')
                ])
                
                failed_registrations = self.env['pms.guest.registration'].search_count([
                    ('property_id', '=', property_rec.id),
                    ('create_date', '>=', week_start),
                    ('state', '=', 'error')
                ])
                
                total_guests = sum(registrations.mapped('guest_count'))
                success_rate = 100.0 if not failed_registrations else (len(registrations) / (len(registrations) + failed_registrations)) * 100
                
                # Get top nationalities
                guests = self.env['pms.checkin.partner'].search([
                    ('it_registered', '=', True),
                    ('it_registration_date', '>=', week_start),
                    ('pms_property_id', '=', property_rec.id)
                ])
                
                nationality_stats = {}
                for guest in guests:
                    if guest.nationality_id:
                        country = guest.nationality_id.name
                        nationality_stats[country] = nationality_stats.get(country, 0) + 1
                
                top_nationalities = [
                    {
                        'country': country,
                        'count': count,
                        'percentage': (count / total_guests * 100) if total_guests > 0 else 0
                    }
                    for country, count in sorted(nationality_stats.items(), key=lambda x: x[1], reverse=True)[:5]
                ]
                
                # Prepare context for email
                email_context = {
                    'total_registrations': len(registrations),
                    'total_guests': total_guests,
                    'failed_registrations': failed_registrations,
                    'success_rate': success_rate,
                    'top_nationalities': top_nationalities,
                    'avg_response_time': '&lt; 2 seconds',  # Could be calculated from actual data
                }
                
                # Send email
                template = self.env.ref('pms_l10n_it.email_template_weekly_summary', raise_if_not_found=False)
                if template:
                    template.with_context(**email_context).send_mail(property_rec.id)
                    
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.error("Error generating weekly summary for property %s: %s", property_rec.name, str(e))
