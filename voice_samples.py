"""Graba la misma narración con varias voces de Gemini (español de España) para elegir la favorita.
Salida: out/voices/<Voz>.mp3. La ganadora se pone en Settings > Secrets and variables > Actions > Variables > GEMINI_VOICE."""
import os, subprocess
import numpy as np, soundfile as sf
import voice

VOICES = ["Orus", "Puck", "Charon", "Fenrir", "Sadachbia", "Algieba", "Iapetus", "Alnilam", "Sadaltager", "Achird",
          "Algenib", "Umbriel"]                                                                    # masculinas
TEXTS = ["¿Te sabes esta pregunta de normativa? Ojo, que tiene trampa.",
         "Según el DB SI del CTE, la evacuación de ocupantes se justifica en el proyecto.",
         "La correcta es la B. Y en un proyecto real, este error sale caro.",
         "Y si vas justo de equipo, delega el proyecto: presupuesto cerrado en 24 horas en uniondearquitectos.com."]
STYLES = ["punchy, confident challenge", "clear, assured, explaining", "confident, a hint of a smile", "warm, persuasive"]
os.makedirs("out/voices", exist_ok=True)


def save(name, clips):
    a = np.concatenate([np.concatenate([c, np.zeros(int(voice.SR * .3), np.float32)]) for c in clips])
    sf.write("out/voices/tmp.wav", a, voice.SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "out/voices/tmp.wav", "-b:a", "128k", f"out/voices/{name}.mp3"], check=True)


if os.environ.get("ELEVENLABS_API_KEY"):           # voces de ElevenLabs (las IDs separadas por comas en ELEVENLABS_VOICE_IDS)
    ids = [x.strip() for x in os.environ.get("ELEVENLABS_VOICE_IDS", os.environ.get("ELEVENLABS_VOICE_ID", "")).split(",") if x.strip()]
    for vid in ids or [None]:
        try:
            if vid: os.environ["ELEVENLABS_VOICE_ID"] = vid
            voice._EVOICE.clear()
            save(f"ElevenLabs_{vid or 'auto'}", voice._eleven_many(TEXTS)); print("ok elevenlabs", vid, flush=True)
        except Exception as e:
            print("FALLÓ elevenlabs", vid, e, flush=True)
os.environ.pop("ELEVENLABS_API_KEY", None)        # el resto de muestras, con Gemini
for v in VOICES:
    voice.GEMINI_VOICE = v
    voice.reset()
    try:
        clips = voice.say_many(TEXTS, styles=STYLES)
        if voice.ENGINE_USED != "gemini":
            raise RuntimeError("Gemini TTS no disponible")
        a = np.concatenate([np.concatenate([c, np.zeros(int(voice.SR * .3), np.float32)]) for c in clips])
        sf.write("out/voices/tmp.wav", a, voice.SR)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "out/voices/tmp.wav", "-b:a", "128k", f"out/voices/{v}.mp3"], check=True)
        print("ok", v, flush=True)
    except Exception as e:
        print("FALLÓ", v, e, flush=True)
if os.path.exists("out/voices/tmp.wav"): os.remove("out/voices/tmp.wav")
