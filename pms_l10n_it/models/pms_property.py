# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    remote_checkin_reminder_hours = fields.Integer(
        string="Remote Check-in Reminder Hours",
        default=72,
        help="Number of hours before check-in to send remote check-in reminder"
    )

    @api.depends("id")
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