# Privacidad y seguridad

No se almacenan nombre, email, teléfono ni DNI de clientes. Game Masters usan IDs internos. Contraseñas se hashean con Argon2; secretos viven en `.env` excluido. Los roles previstos son admin, dirección y analista. **PENDIENTE DE PRODUCCIÓN:** autenticación por sesión/JWT, autorización por endpoint, rotación de secretos, auditoría y política de retención.

Los nombres visibles de Game Masters DEMO no representan empleados. Al importar personal real debe existir base legítima, minimización, control de acceso y una política explícita contra rankings laborales automáticos.
