# Approved VectorCraft icon transfer

The exact original user-approved PNG from VectorCraft_Approved_Vc_Icon_Kit.zip is now committed at assets/branding/vectorcraft/vc-glass-approved.png. SHA256291c7768cabaf4419082abfbd100a17668e9c7c4ca8a57fa45667f0f7233dbc2; 1254x1254 RGBA; 1700675 bytes. No resize/recolour/substitution performed. Existing verify_approved_icon.py gate can now validate it.

This fixes only the missing approved-artwork gate. It does not enable the public branch's older direct-secret signing job. Active established identity/encrypted backup live in the private VectorCraft repository and must be preserved. A later enhancement APK needs a private isolated build/sign integration, same-run source/hash/payload verification and durable versionCode above prior signed baseline. Device testing and publication remain pending. Other app branches are unchanged.
