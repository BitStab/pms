# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _


class PmsCheckinPartner(models.Model):
    _inherit = "pms.checkin.partner"

    # Italian registration fields
    it_registered = fields.Boolean(
        string="Registered with Italian Police",
        default=False,
        help="Indicates if this guest has been registered with Italian Police (Alloggiati Web)"
    )
    
    it_registration_date = fields.Datetime(
        string="Registration Date",
        help="Date and time when the guest was registered with Italian Police"
    )
    
    it_exemption_reason = fields.Selection([
        ('minor', 'Minor under 14'),
        ('diplomatic', 'Diplomatic personnel'),
        ('military', 'Military personnel'),
        ('other', 'Other exemption'),
    ], string="Exemption Reason", help="Reason for exemption from registration")
    
    it_exemption_notes = fields.Text(
        string="Exemption Notes",
        help="Additional notes for exemption"
    )

    alloggiati_document_type = fields.Char(
        string="Alloggiati Document Type Code",
        compute="_compute_alloggiati_document_type",
        store=True,
        help="Document type code for Alloggiati Web service"
    )

    residence_city_id = fields.Many2one("res.city", string="City of Residence")

    guest_group_id = fields.Many2one(
        "pms.guest.group",
        string="Guest Group"
    )
    
    is_main_guest = fields.Boolean(
        string="Main Guest (Capo)",
        default=False
    )
    
    tipo_alloggiato_code = fields.Selection([
        ('16', 'Hotel Guest (Standard)'),
        ('17', 'Capo Famiglia'),
        ('18', 'Familiare'),
        ('19', 'Capo Gruppo'),
        ('20', 'Membro Gruppo')
    ], string="Guest Type", compute="_compute_tipo_alloggiato")

    self_checkin_completed = fields.Boolean(
        string="Self Check-in Completed",
        default=False
    )    
    
    @api.depends('document_type', 'document_type.alloggiati_code')
    def _compute_alloggiati_document_type(self):
        """Compute Alloggiati document type code"""
        for record in self:
            if record.document_type and record.document_type.alloggiati_code:
                record.alloggiati_document_type = record.document_type.alloggiati_code
            else:
                record.alloggiati_document_type = ""

    def get_alloggiati_document_data(self):
        """Get document data formatted for Alloggiati submission"""
        self.ensure_one()
        return {
            'document_type': self.alloggiati_document_type or "",
            'document_number': self.document_number or "",
            'document_expedition_date': self.document_expedition_date or "",
            'document_country': self.document_country_id.code if self.document_country_id else "",
        }

    @api.depends('guest_group_id', 'is_main_guest')
    def _compute_tipo_alloggiato(self):
        """Automatische Bestimmung des Tipo Alloggiato"""
        for guest in self:
            if not guest.guest_group_id:
                guest.tipo_alloggiato_code = '16'  # Standard
                continue
                
            group_type = guest.guest_group_id.group_type
            
            if guest.is_main_guest:
                if group_type == 'family':
                    guest.tipo_alloggiato_code = '17'  # Capo Famiglia
                elif group_type == 'group':
                    guest.tipo_alloggiato_code = '19'  # Capo Gruppo
                else:
                    guest.tipo_alloggiato_code = '16'  # Standard
            else:
                if group_type == 'family':
                    guest.tipo_alloggiato_code = '18'  # Familiare
                elif group_type == 'group':
                    guest.tipo_alloggiato_code = '20'  # Membro Gruppo
                else:
                    guest.tipo_alloggiato_code = '16'  # Standard
    

    @api.model
    def _get_document_type_selection(self):
        """Get dynamic document type selection"""
        try:
            return self.env['pms.document.type'].get_selection_list()
        except:
            # Fallback für Kompatibilität
            return [('1', 'Passport'), ('2', 'ID Card'), ...]

    def action_register_guest(self):
        """Open wizard to register this guest with Italian Police"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Guest'),
            'res_model': 'pms.guest.registration.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_property_id': self.pms_property_id.id,
                'default_checkin_partner_ids': [(6, 0, self.ids)],
            }
        }
    
    def action_mark_as_registered(self):
        """Mark guest as registered manually"""
        self.write({
            'it_registered': True,
            'it_registration_date': fields.Datetime.now()
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Guest Registered'),
                'message': _('Guest marked as registered successfully!'),
                'type': 'success',
            }
        }
    
    def action_unmark_as_registered(self):
        """Unmark guest as registered"""
        self.write({
            'it_registered': False,
            'it_registration_date': False
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Guest Unregistered'),
                'message': _('Guest registration status removed!'),
                'type': 'info',
            }
        }