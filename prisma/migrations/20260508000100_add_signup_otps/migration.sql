CREATE TABLE IF NOT EXISTS "signup_otps" (
    "id" SERIAL PRIMARY KEY,
    "email" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "otp_hash" TEXT NOT NULL,
    "expires_at" TIMESTAMPTZ NOT NULL,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "verified" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "signup_otps_email_idx" ON "signup_otps"("email");
CREATE INDEX IF NOT EXISTS "signup_otps_phone_idx" ON "signup_otps"("phone");
CREATE INDEX IF NOT EXISTS "signup_otps_role_idx" ON "signup_otps"("role");
CREATE INDEX IF NOT EXISTS "signup_otps_expires_at_idx" ON "signup_otps"("expires_at");
CREATE INDEX IF NOT EXISTS "signup_otps_verified_idx" ON "signup_otps"("verified");
CREATE INDEX IF NOT EXISTS "signup_otps_created_at_idx" ON "signup_otps"("created_at");
