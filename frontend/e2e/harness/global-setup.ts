/** Starts the run from nothing recorded.
 *
 *  The coverage gate reads a directory of files the tests wrote. Left over from
 *  a previous run, those files would credit this one with actions it never
 *  fired — which is the one failure mode a coverage gate cannot have, because
 *  it turns green by remembering rather than by testing.
 */
import fs from "node:fs";
import { RECORD_DIR } from "./recorder";

export default function clearRecordings(): void {
  fs.rmSync(RECORD_DIR, { recursive: true, force: true });
}
