// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import Groq from "npm:groq-sdk@0.26.0";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

function getGroqClient(): Groq {
  const apiKey = Deno.env.get("GROQ_API_KEY");
  if (!apiKey) {
    throw new Error("Missing GROQ_API_KEY");
  }
  return new Groq({ apiKey });
}

async function transcribeAudio(groq: Groq, audioFile: File): Promise<string> {
  const transcription = await groq.audio.transcriptions.create({
    file: audioFile,
    model: "whisper-large-v3-turbo",
    temperature: 0,
    response_format: "verbose_json",
  });
  return transcription.text?.trim() || "";
}

serve(async (req) => {
  if (req.method === "OPTIONS") return jsonResponse({ ok: true });

  // Verify auth
  const authHeader = req.headers.get("authorization");
  if (!authHeader) {
    return jsonResponse({ error: "Missing authorization header" }, 401);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    global: { headers: { Authorization: authHeader } },
  });

  const { data: { user }, error: authError } = await supabase.auth.getUser();
  if (authError || !user) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }

  try {
    const groq = getGroqClient();

    const formData = await req.formData();
    const audioFile = formData.get("audio") as File | null;
    const task = (formData.get("task") as string) || "transcribe_and_write";
    const context = (formData.get("context") as string) || "";
    const example = (formData.get("example") as string) || "";
    const existingValue = (formData.get("existingValue") as string) || "";

    if (!audioFile) {
      return jsonResponse({ error: "audio file is required" }, 400);
    }

    // Step 1: Transcribe audio
    const transcribedText = await transcribeAudio(groq, audioFile);

    if (!transcribedText) {
      return jsonResponse({ error: "No speech detected in audio" }, 400);
    }

    if (task === "transcribe_only") {
      return jsonResponse({
        success: true,
        transcription: transcribedText,
        usage: null,
      });
    }

    // Step 2: Rewrite with LLM
    const systemMsg = `You clean up speech-to-text output. Your ONLY job is minimal cleanup — the result should sound like the person wrote it themselves.

Rules:
- Remove filler words (um, uh, like, you know, so, basically, I mean)
- Add punctuation and fix obvious grammar mistakes
- That's it. Do NOT rewrite, rephrase, restructure, or polish
- Keep their exact words, sentence structure, and casual tone
- Keep contractions, slang, and informal language as-is
- Do NOT make it sound more professional, articulate, or formal
- Do NOT combine or reorganize sentences
- If in doubt, leave it closer to what they said`;

    let userMsg = `Transform this spoken input into clean written notes.

SPOKEN INPUT: "${transcribedText}"
${existingValue ? `\nEXISTING NOTES: "${existingValue}"\n(The user may want to modify, extend, or replace this)` : ""}
${context ? `\nCONTEXT: ${context}\n` : ""}${example ? `\nEXAMPLE: "${example}"\n` : ""}
Output ONLY the final text, no commentary or quotes:`;

    let resp;
    try {
      resp = await groq.chat.completions.create({
        model: "moonshotai/kimi-k2-instruct",
        messages: [
          { role: "system", content: systemMsg },
          { role: "user", content: userMsg },
        ],
        temperature: 0.3,
        max_tokens: 2048,
        top_p: 1,
      });
    } catch {
      return jsonResponse({
        success: true,
        transcription: transcribedText,
        prompt: transcribedText,
        usage: null,
        warning: "AI enhancement failed, returning raw transcription",
      });
    }

    const promptText = resp.choices[0]?.message?.content?.trim() || transcribedText;

    return jsonResponse({
      success: true,
      transcription: transcribedText,
      prompt: promptText,
      usage: resp.usage,
    });
  } catch (err: unknown) {
    return jsonResponse(
      { error: "Internal server error", details: (err as Error)?.message },
      500
    );
  }
});
