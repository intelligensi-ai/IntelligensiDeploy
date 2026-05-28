import { FormEvent, useState } from "react";
import { knownLocations } from "../data/mockCityConditions";
import { ChatMessage, ParsedIntent, UserProfile } from "../types";

interface ChatSidebarProps {
  messages: ChatMessage[];
  intent: ParsedIntent;
  profile: UserProfile;
  onSubmit: (text: string) => void;
  onProfileChange: (profile: UserProfile) => void;
}

const promptChips = [
  "Find AI networking events tonight",
  "Something cultural under GBP25",
  "Best event after work near Canary Wharf",
  "Compare tonight's startup events",
  "Low-effort social events this weekend"
];

const splitList = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export function ChatSidebar({ messages, intent, profile, onSubmit, onProfileChange }: ChatSidebarProps) {
  const [draft, setDraft] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("Speak");

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!draft.trim()) return;
    onSubmit(draft.trim());
    setDraft("");
  };

  const handleVoice = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceStatus("Unavailable");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-GB";
    recognition.interimResults = false;
    recognition.onstart = () => setVoiceStatus("Listening");
    recognition.onend = () => setVoiceStatus("Speak");
    recognition.onerror = () => setVoiceStatus("Retry");
    recognition.onresult = (event: any) => {
      const transcript = event.results?.[0]?.[0]?.transcript;
      if (transcript) setDraft(transcript);
    };
    recognition.start();
  };

  return (
    <aside className="chat-panel">
      <div className="chat-header">
        <div>
          <p className="eyebrow">Conversational intent</p>
          <h2>Speak your intent</h2>
        </div>
        <button type="button" className="icon-button" onClick={handleVoice} title="Voice input">
          {voiceStatus}
        </button>
      </div>

      <div className="prompt-chips">
        {promptChips.map((chip) => (
          <button type="button" key={chip} onClick={() => onSubmit(chip)}>
            {chip}
          </button>
        ))}
      </div>

      <div className="chat-messages" aria-live="polite">
        {messages.map((message) => (
          <article key={message.id} className={`message ${message.role}`}>
            <span>{message.role === "user" ? "You" : "Signal"}</span>
            <p>{message.text}</p>
          </article>
        ))}
      </div>

      {intent.missingContext.length > 0 && (
        <div className="context-nudge">
          Missing context: {intent.missingContext.join(", ")}.
        </div>
      )}

      <form className="chat-input" onSubmit={submit}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="I want to meet AI investors and senior engineers tonight after work from Aldgate under GBP30."
          rows={4}
        />
        <button type="submit">Run Signal</button>
      </form>

      <div className="profile-panel">
        <button type="button" className="profile-toggle" onClick={() => setProfileOpen((open) => !open)}>
          User profile
          <span>{profileOpen ? "Hide" : "Edit"}</span>
        </button>

        {profileOpen && (
          <div className="profile-form">
            <label>
              Name
              <input
                value={profile.name}
                onChange={(event) => onProfileChange({ ...profile, name: event.target.value })}
              />
            </label>
            <label>
              Email
              <input
                value={profile.email}
                onChange={(event) => onProfileChange({ ...profile, email: event.target.value })}
              />
            </label>
            <label>
              Phone
              <input
                value={profile.phone}
                onChange={(event) => onProfileChange({ ...profile, phone: event.target.value })}
              />
            </label>
            <div className="profile-grid">
              <label>
                Home
                <select
                  value={profile.homeLocation}
                  onChange={(event) => onProfileChange({ ...profile, homeLocation: event.target.value })}
                >
                  {knownLocations.map((location) => (
                    <option key={location.name}>{location.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Work
                <select
                  value={profile.workLocation}
                  onChange={(event) => onProfileChange({ ...profile, workLocation: event.target.value })}
                >
                  {knownLocations.map((location) => (
                    <option key={location.name}>{location.name}</option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Budget preference
              <input
                type="number"
                min="0"
                value={profile.budgetPreference}
                onChange={(event) =>
                  onProfileChange({ ...profile, budgetPreference: Number(event.target.value) })
                }
              />
            </label>
            <label>
              Event interests
              <input
                value={profile.interests.join(", ")}
                onChange={(event) => onProfileChange({ ...profile, interests: splitList(event.target.value) })}
              />
            </label>
            <label>
              Networking goals
              <input
                value={profile.networkingGoals.join(", ")}
                onChange={(event) =>
                  onProfileChange({ ...profile, networkingGoals: splitList(event.target.value) })
                }
              />
            </label>
          </div>
        )}
      </div>
    </aside>
  );
}
