import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "../components/ui/button.jsx";
import { Card } from "../components/ui/card.jsx";
import {
  Container,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from "../components/ui/layout.jsx";
import { Typography } from "../components/ui/typography.jsx";

const seasons = [2021, 2022, 2023, 2024, 2025];

export default function RaceExplorer() {
  const [season, setSeason] = useState(2021);
  const [races, setRaces] = useState([]);
  const [selectedRaceId, setSelectedRaceId] = useState(null);
  const [raceDetail, setRaceDetail] = useState(null);
  const [loadingRaces, setLoadingRaces] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadRaces() {
      setLoadingRaces(true);
      setError(null);
      setRaceDetail(null);
      setSelectedRaceId(null);
      try {
        const response = await fetch(`/api/races?season=${season}`);
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || `Request failed (${response.status})`);
        }
        const data = await response.json();
        if (!cancelled) setRaces(Array.isArray(data) ? data : []);
      } catch (err) {
        if (!cancelled) {
          setRaces([]);
          setError(err.message || "Unable to load races.");
        }
      } finally {
        if (!cancelled) setLoadingRaces(false);
      }
    }

    loadRaces();
    return () => {
      cancelled = true;
    };
  }, [season]);

  async function loadRaceDetail(raceId) {
    setSelectedRaceId(raceId);
    setLoadingDetail(true);
    setError(null);
    try {
      const response = await fetch(`/api/races/${raceId}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${response.status})`);
      }
      setRaceDetail(await response.json());
    } catch (err) {
      setRaceDetail(null);
      setError(err.message || "Unable to load race results.");
    } finally {
      setLoadingDetail(false);
    }
  }

  return (
    <Container>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <Typography variant="h4" className="mb-1">
            Race Explorer
          </Typography>
          <Typography variant="body2" className="text-gray-400">
            Browse races and full classifications for a season.
          </Typography>
        </div>

        <div className="flex gap-2">
          {seasons.map((year) => (
            <button
              key={year}
              type="button"
              onClick={() => setSeason(year)}
              className={`rounded-md border px-3 py-1.5 text-sm ${
                season === year
                  ? "border-accent bg-accent/15 text-accent"
                  : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
              }`}
            >
              {year}
            </button>
          ))}
        </div>
      </div>

      {loadingRaces && (
        <div className="flex items-center justify-center gap-3 py-16 text-gray-400">
          <Spinner size={28} />
          Loading races...
        </div>
      )}

      {!loadingRaces && error && (
        <Card className="mb-6 border-red-500/30 bg-red-500/5">
          <Typography variant="body2" className="text-red-300">
            {error}. Make sure the backend is running on port 8000.
          </Typography>
        </Card>
      )}

      {!loadingRaces && !error && (
        <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <Card>
            <Typography variant="h5" className="mb-4">
              {season} Races
            </Typography>
            {races.length === 0 ? (
              <Typography variant="body2" className="text-gray-500">
                No races found for this season.
              </Typography>
            ) : (
              <ul className="max-h-[560px] space-y-1 overflow-y-auto">
                {races.map((race) => (
                  <li key={race.race_id}>
                    <button
                      type="button"
                      onClick={() => loadRaceDetail(race.race_id)}
                      className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm ${
                        selectedRaceId === race.race_id
                          ? "bg-accent/15 text-accent"
                          : "text-gray-300 hover:bg-gray-800"
                      }`}
                    >
                      <span>
                        <span className="mr-2 text-gray-500">R{race.round}</span>
                        {race.race_name}
                      </span>
                      <span className="text-xs text-gray-500">{race.date}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <div className="mb-4 flex items-center justify-between gap-3">
              <Typography variant="h5">Race Results</Typography>
              {selectedRaceId && (
                <Button
                  type="button"
                  onClick={() => loadRaceDetail(selectedRaceId)}
                  className="flex items-center gap-1 border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:border-gray-500"
                >
                  <RefreshCw size={13} />
                  Refresh
                </Button>
              )}
            </div>

            {!selectedRaceId && (
              <Typography variant="body2" className="text-gray-500">
                Select a race to view its classification.
              </Typography>
            )}

            {loadingDetail && (
              <div className="flex items-center gap-3 py-8 text-gray-400">
                <Spinner size={20} />
                Loading results...
              </div>
            )}

            {!loadingDetail && selectedRaceId && raceDetail && (
              <>
                <Typography variant="body2" className="mb-3 text-gray-500">
                  {raceDetail.result_count ?? raceDetail.results?.length ?? 0} classified entries
                </Typography>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell className="text-xs uppercase text-gray-400">Pos</TableCell>
                      <TableCell className="text-xs uppercase text-gray-400">Driver</TableCell>
                      <TableCell className="text-xs uppercase text-gray-400">Constructor</TableCell>
                      <TableCell className="text-right text-xs uppercase text-gray-400">Points</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(raceDetail.results || []).map((result, index) => (
                      <TableRow key={`${result.driver_id || result.driver_name}-${index}`}>
                        <TableCell>{result.position || "—"}</TableCell>
                        <TableCell className="text-white">{result.driver_name || "—"}</TableCell>
                        <TableCell className="text-gray-400">
                          {result.constructor_name || "—"}
                        </TableCell>
                        <TableCell className="text-right">{result.points ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            )}
          </Card>
        </div>
      )}
    </Container>
  );
}
