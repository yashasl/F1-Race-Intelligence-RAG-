import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Card } from "../components/ui/card.jsx";
import { Container } from "../components/ui/layout.jsx";
import { Typography } from "../components/ui/typography.jsx";

export default function AboutPage() {
  const [showMethodology, setShowMethodology] = useState(false);

  return (
    <Container maxW="4xl">
      <Typography variant="h4" className="mb-2">
        About F1 Performance Analytics
      </Typography>
      <Typography variant="body2" className="mb-8 text-gray-400">
        An interactive platform for exploring historical Formula 1 data from the
        2021–2025 seasons.
      </Typography>

      <div className="space-y-6">
        <Section title="Project Purpose">
          An interactive web application for exploring historical Formula 1 data
          from the 2021–2025 seasons. The platform combines semantic search with
          structured data analysis to provide grounded, evidence-based answers
          about F1 races, drivers, constructors, and championships.
        </Section>

        <Section title="Data Coverage">
          The dataset covers all Formula 1 championship races from the 2021
          through 2025 seasons, including results, qualifying sessions, pit
          stops, driver and constructor standings, lap times, and related
          statistics. All data is sourced from official F1 championship records.
        </Section>

        <Card>
          <button
            type="button"
            className="flex w-full items-center justify-between gap-3 text-left"
            onClick={() => setShowMethodology((value) => !value)}
          >
            <Typography variant="h5">How Semantic Retrieval Works</Typography>
            {showMethodology ? (
              <ChevronUp size={18} className="text-gray-400" />
            ) : (
              <ChevronDown size={18} className="text-gray-400" />
            )}
          </button>

          {showMethodology && (
            <div className="mt-4 space-y-3">
              <Typography variant="body2" className="text-gray-300">
                The system uses Sentence Transformers (all-MiniLM-L6-v2) to
                generate 384-dimensional embeddings from F1 race documents. User
                queries are also embedded and compared against the Pinecone
                vector index using cosine similarity.
              </Typography>
              <Typography variant="body2" className="text-gray-300">
                Relevant documents are retrieved and used as grounded evidence
                for the Gemini LLM, ensuring answers are based on actual dataset
                records rather than hallucinated information.
              </Typography>
            </div>
          )}
        </Card>

        <Section title="Pinecone & Gemini Integration">
          Pinecone provides semantic search over the embedded F1 documents. When
          a user asks a question, the system retrieves the most relevant
          documents, filters out those with empty metadata, and passes the
          grounded context to the Gemini API (configured via GEMINI_API_KEY).
          Gemini then generates an answer citing the specific source records
          used, or states when evidence is insufficient.
        </Section>

        <Section title="Data Limitations">
          <ul className="list-inside list-disc space-y-1">
            <li>Coverage is limited to the 2021–2025 F1 championship seasons.</li>
            <li>
              Some statistics may have missing data (for example, lap times for
              all drivers or all practice sessions).
            </li>
            <li>
              Pre-season testing, non-championship races, and historical data
              prior to 2021 are not included.
            </li>
            <li>
              AI-generated answers are grounded in retrieved evidence but should
              be verified against official F1 sources for critical use.
            </li>
          </ul>
        </Section>

        <div className="border-t border-gray-800 pt-4">
          <Typography variant="caption" className="block">
            Version 1.0.0
          </Typography>
          <Typography variant="caption" className="block text-gray-500">
            F1 Performance Analytics Platform · 2026
          </Typography>
        </div>
      </div>
    </Container>
  );
}

function Section({ title, children }) {
  return (
    <Card>
      <Typography variant="h5" className="mb-3">
        {title}
      </Typography>
      <Typography variant="body2" className="leading-relaxed text-gray-300">
        {children}
      </Typography>
    </Card>
  );
}
