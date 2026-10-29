// The stage's shared parts, used by both views (WP3-1). Each is one component with props for data
// and words and a `data-role` on what a fidelity check measures. Base styles are neutral and thin
// (parts.css); each view skins them under its own `[data-stage-view=...]` root.
import "./parts.css";

export { Composer, Echo, EnoughButton, Question, ReplyNotice, RevisitBanner, StillNeeds, Suggestions } from "./Ask";
export { CheckCard, LineAdder, RunTestButton } from "./Check";
export { DESCRIBE_WORDS, Describe } from "./Describe";
export { StageSeal, StepRail } from "./Frame";
export { FiledCards, PhaseList, PracticeTile, ProblemList, RunProgress, clock } from "./Later";
export { KindGlyph, KindLabel, NeedSentence, PieceCard, UndoToast } from "./Piece";
export { SavedCard, ScoreLine, VerdictActions, VerdictRows } from "./Score";
