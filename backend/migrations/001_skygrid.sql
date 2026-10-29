CREATE TABLE IF NOT EXISTS skygrid.group_invites (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 group_id UUID NOT NULL REFERENCES skygrid.groups(id) ON DELETE CASCADE,
 token_hash TEXT UNIQUE NOT NULL,
 created_by UUID NOT NULL REFERENCES skygrid.users(id) ON DELETE CASCADE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 expires_at TIMESTAMPTZ NOT NULL,
 used_at TIMESTAMPTZ,
 used_by UUID REFERENCES skygrid.users(id) ON DELETE SET NULL
);
