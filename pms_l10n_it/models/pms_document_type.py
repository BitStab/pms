# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)


class DocumentType(models.Model):
    _name = "pms.document.type"
    _description = "Document Types from Alloggiati Web"
    _order = "sequence, name"
    
    # Check if OCA PMS already has document_type functionality
    @api.model
    def _check_oca_compatibility(self):
        """Check if OCA PMS already has document_type functionality"""
        # This method can be extended if OCA PMS gets document_type support
        return hasattr(self.env['pms.checkin.partner'], 'document_type_id')

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
        help="Document type name (translatable)"
    )
    
    code = fields.Char(
        string="Alloggiati Code",
        required=True,
        help="Official code from Alloggiati Web"
    )
    
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence for ordering"
    )
    
    active = fields.Boolean(
        string="Active",
        default=True
    )
    
    # Technical fields for mapping
    alloggiati_table_id = fields.Many2one(
        "alloggiati.table",
        string="Alloggiati Table Record",
        help="Link to the alloggiati table record"
    )
    
    # OCA PMS Compatibility
    is_oca_compatible = fields.Boolean(
        string="OCA Compatible",
        compute="_compute_oca_compatible",
        help="Indicates if this document type is compatible with OCA PMS standards"
    )
    
    @api.depends()
    def _compute_oca_compatible(self):
        """Compute OCA compatibility status"""
        oca_compatible = self._check_oca_compatibility()
        for record in self:
            record.is_oca_compatible = oca_compatible
    
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Document type code must be unique!'),
    ]

    @api.model
    def get_selection_list(self):
        """Get selection list for document_type field"""
        records = self.search([('active', '=', True)])
        return [(rec.code, rec.name) for rec in records]

    @api.model
    def sync_from_alloggiati_tables(self):
        """Sync document types from alloggiati.table"""
        # Get all document types from alloggiati tables
        alloggiati_docs = self.env['alloggiati.table'].search([
            ('table_type', '=', 'tipi_documento'),
            ('active', '=', True)
        ])
        
        synced_count = 0
        
        for doc in alloggiati_docs:
            # Check if document type already exists
            existing = self.search([('code', '=', doc.code)], limit=1)
            
            if existing:
                # Update existing
                existing.write({
                    'name': doc.name,
                    'alloggiati_table_id': doc.id,
                    'active': doc.active
                })
            else:
                # Create new
                self.create({
                    'name': doc.name,
                    'code': doc.code,
                    'alloggiati_table_id': doc.id,
                    'active': doc.active,
                    'sequence': synced_count * 10
                })
            
            synced_count += 1
        
        _logger.info("Synced %d document types from Alloggiati tables", synced_count)
        return synced_count

    @api.model
    def get_code_by_name(self, name):
        """Get document type code by name (for backward compatibility)"""
        if not name:
            return ""
        
        # First try exact match
        doc_type = self.search([
            ('name', '=', name),
            ('active', '=', True)
        ], limit=1)
        
        if doc_type:
            return doc_type.code
        
        # Try case-insensitive match
        doc_type = self.search([
            ('name', 'ilike', name),
            ('active', '=', True)
        ], limit=1)
        
        if doc_type:
            return doc_type.code
        
        # Fallback to old mapping
        type_mappings = {
            "passport": "1",
            "id_card": "2", 
            "driving_license": "3",
            "other": "4"
        }
        return type_mappings.get(name.lower(), "")

    def name_get(self):
        """Custom name_get to show code and name"""
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}"
            result.append((record.id, name))
        return result