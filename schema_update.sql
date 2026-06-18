CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    total_records INTEGER DEFAULT 0,
    quality_score INTEGER DEFAULT 0,
    json_file_url TEXT,
    pdf_file_url TEXT,
    status TEXT DEFAULT 'completed'
);

-- Note: Also ensure that a Storage Bucket named 'exports' exists in your Supabase project.
-- It can be public or private depending on your security needs, but private is recommended.
