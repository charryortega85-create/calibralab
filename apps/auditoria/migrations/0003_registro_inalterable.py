"""
RNF-12: el registro de cambios no se modifica ni se borra, ni siquiera fuera de Django.
Un trigger de PostgreSQL rechaza cualquier UPDATE, DELETE o TRUNCATE sobre la tabla.
"""
from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION auditoria_registro_inalterable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'El registro de cambios no se puede modificar ni borrar (RNF-12)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auditoria_registro_sin_cambios
    BEFORE UPDATE OR DELETE ON auditoria_registrocambio
    FOR EACH ROW EXECUTE FUNCTION auditoria_registro_inalterable();

CREATE TRIGGER auditoria_registro_sin_vaciado
    BEFORE TRUNCATE ON auditoria_registrocambio
    FOR EACH STATEMENT EXECUTE FUNCTION auditoria_registro_inalterable();
"""

QUITAR = """
DROP TRIGGER IF EXISTS auditoria_registro_sin_vaciado ON auditoria_registrocambio;
DROP TRIGGER IF EXISTS auditoria_registro_sin_cambios ON auditoria_registrocambio;
DROP FUNCTION IF EXISTS auditoria_registro_inalterable();
"""


class Migration(migrations.Migration):
    dependencies = [("auditoria", "0002_initial")]

    operations = [migrations.RunSQL(CREAR, QUITAR)]
