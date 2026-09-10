# Field-level PHI encryption (F-015) — operator guide

What is covered: `patient` and `reception_intake` **date_of_birth, address,
nok_phone (+ nok_address on patient)** are stored as Fernet ciphertext once a
key is configured. A stolen dump / backup zip shows only ciphertext for these
columns. `patient.phone` stays a plain, indexed column on purpose — it is the
number the hospital dials and searches by partial match every day.

## Turn it on (Render)

1. Generate a key **once** and store it somewhere safe (password manager).
   Losing it makes the encrypted columns permanently unreadable — there is no
   recovery without it.

   ```
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. Add `FIELD_ENCRYPTION_KEY = <that value>` to the web service environment
   and deploy. The app keeps working immediately: old rows are read as
   plaintext and re-encrypted the next time they are written.

3. Backfill everything in one pass (Render shell):

   ```
   python -m app.encrypt_phi_backfill
   ```

   Idempotent — run it again any time; it reports how many rows were still
   plaintext.

## Behaviour changes to know

- NOK-phone **search** matches the full normalised number (blind index,
  `nok_phone_bx`) instead of any 4+ digit substring. Substring search on
  ciphertext is impossible by design — that is the point.
- Backups (CSV) contain ciphertext for these columns; the restore drill
  restores them byte-identically.
- **Never rotate `FIELD_ENCRYPTION_KEY` casually.** Values are only readable
  under the key that encrypted them. A deliberate rotation needs a
  decrypt-with-old / re-encrypt-with-new migration.
- Tests exercise both modes (`tests/test_f015_field_encryption.py`): the
  codebase keeps working with no key set.
