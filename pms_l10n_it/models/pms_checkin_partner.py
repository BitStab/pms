# Copyright 2024 Your Company
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
    
    # Additional fields that might be required for Italian registration
    document_type = fields.Selection(
        selection='_get_document_type_selection',
        string="Document Type"
    )
    
    document_number = fields.Char(
        string="Document Number",
        help="Document number for identification"
    )
    
    document_expedition_date = fields.Date(
        string="Document Expedition Date",
        help="Date when the document was issued"
    )

    residence_city_id = fields.Many2one("res.city", string="City of Residence")

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