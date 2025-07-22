# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)


class ResPartnerIdCategory(models.Model):
    _inherit = "res.partner.id_category"
    
    # Alloggiati-spezifische Erweiterungen zu bestehendem PMS-Modell
    alloggiati_code = fields.Char(
        string="Alloggiati Code",
        help="Official code from Alloggiati Web service"
    )
    
    alloggiati_table_id = fields.Many2one(
        "alloggiati.table",
        string="Alloggiati Table Record",
        help="Link to the alloggiati table record"
    )
    
    is_alloggiati_type = fields.Boolean(
        string="Is Alloggiati Type",
        compute="_compute_is_alloggiati_type",
        store=True,
        help="Indicates if this category is synchronized with Alloggiati"
    )
    
    _sql_constraints = [
        ('unique_alloggiati_code', 
         'unique(alloggiati_code)', 
         'Alloggiati code must be unique!'),
    ]

    @api.depends('alloggiati_code')
    def _compute_is_alloggiati_type(self):
        """Compute if this is an Alloggiati document type"""
        for record in self:
            record.is_alloggiati_type = bool(record.alloggiati_code)

    @api.model
    def sync_from_alloggiati_tables(self):
        """Sync document types from alloggiati.table"""
        alloggiati_docs = self.env['alloggiati.table'].search([
            ('table_type', '=', 'tipi_documento'),
            ('active', '=', True)
        ])
        
        synced_count = 0
        for doc in alloggiati_docs:
            existing = self.search([('alloggiati_code', '=', doc.code)], limit=1)
            
            if existing:
                # Update existing
                existing.write({
                    'name': doc.name,
                    'alloggiati_table_id': doc.id,
                    'active': doc.active
                })
            else:
                # Create new - nutzt bestehende PMS-Struktur
                self.create({
                    'name': doc.name,
                    'code': f"IT_DOC_{doc.code}",  # Eindeutiger PMS-Code  
                    'alloggiati_code': doc.code,    # Alloggiati-spezifischer Code
                    'alloggiati_table_id': doc.id,
                    'active': doc.active,
                    'priority': synced_count * 10,  # Nutzt bestehendes PMS-Feld
                    # Nutzt bestehende PMS-Felder: country_ids, etc.
                })
            synced_count += 1
        
        _logger.info("Synced %d document types from Alloggiati", synced_count)
        return synced_count

    @api.model 
    def get_alloggiati_selection(self):
        """Get selection list for Alloggiati document types"""
        alloggiati_types = self.search([
            ('alloggiati_code', '!=', False),
            ('active', '=', True)
        ])
        return [(rec.id, f"[{rec.alloggiati_code}] {rec.name}") for rec in alloggiati_types]

    @api.model
    def find_by_alloggiati_code(self, code):
        """Find document type by Alloggiati code"""
        return self.search([('alloggiati_code', '=', code)], limit=1)

    def name_get(self):
        """Enhanced name_get to show Alloggiati codes"""
        result = []
        for record in self:
            if record.alloggiati_code:
                # Zeige Alloggiati-Code für italienische Dokumenttypen
                name = f"[{record.alloggiati_code}] {record.name}"
            else:
                # Standard PMS-Verhalten für andere Kategorien
                name = f"[{record.code}] {record.name}" if record.code else record.name
            result.append((record.id, name))
        return result

    @api.model
    def create_italian_defaults(self):
        """Create default Italian document types"""
        italian_defaults = [
            {
                'code': 'IT_DOC_1', 
                'alloggiati_code': '1',
                'name': 'Passaporto',
                'priority': 10
            },
            {
                'code': 'IT_DOC_2', 
                'alloggiati_code': '2', 
                'name': 'Carta d\'identità',
                'priority': 20
            },
            {
                'code': 'IT_DOC_3', 
                'alloggiati_code': '3',
                'name': 'Patente di guida', 
                'priority': 30
            },
            {
                'code': 'IT_DOC_4', 
                'alloggiati_code': '4',
                'name': 'Altro documento',
                'priority': 40
            },
        ]
        
        created_count = 0
        for doc_data in italian_defaults:
            existing = self.search([
                ('alloggiati_code', '=', doc_data['alloggiati_code'])
            ], limit=1)
            
            if not existing:
                self.create(doc_data)
                created_count += 1
        
        return created_count

    # Backward compatibility methods für bestehenden pms_l10n_it Code
    @api.model
    def get_selection_list(self):
        """Backward compatibility: Get selection list"""
        return self.get_alloggiati_selection()

    @api.model  
    def get_code_by_name(self, name):
        """Backward compatibility: Get code by name"""
        doc_type = self.search([
            ('name', '=', name),
            ('alloggiati_code', '!=', False),
            ('active', '=', True)
        ], limit=1)
        
        return doc_type.alloggiati_code if doc_type else ""