/**
 * The icon set. One drawing per role, named for the role.
 *
 * What this replaces was emoji, and emoji were never an icon set — they were
 * seventeen glyphs the operating system draws, differently on every one of
 * them. The house is a flat blue outline on Windows, a photographic house on macOS
 * and a beige box on a Linux desktop with no colour font installed; none of the
 * three can be given the accent colour, aligned to a cap height, or made to
 * match the stroke weight of the text beside it. They also carry a size the
 * font decides, which is why every one of them sat in a `text-4xl` or a
 * `text-xs` chosen by eye until it looked right.
 *
 * Lucide draws them as SVG instead: one stroke weight, `currentColor`, and a
 * size that follows the text because the default here is `1em`. That default is
 * the point of this file — an icon placed beside a word lines up with it
 * without a class at the call site, and changing the type scale moves both.
 *
 * The names are roles, not pictures, for the same reason `tone.ts` names roles
 * and not colours: `Delete` survives being redrawn, `Trash2` does not, and a
 * screen that imports `Wallet` to mean "asking price" has hidden the meaning in
 * a call site nobody greps for. Where the same drawing serves two roles it is
 * exported twice — `Sold` and `Rent` are both a key, and they mean different
 * things.
 *
 * Every icon is `aria-hidden` and has no accessible name. That is deliberate
 * and it is the whole accessibility contract of this file: an icon beside a
 * label would otherwise be read out twice, and an icon *without* a label is an
 * `IconButton`, which requires the name as a prop and cannot be built without
 * one. There is no third case.
 *
 * Import from here, never from `lucide-react` directly — the barrel is what
 * keeps one meaning to one drawing across sixty call sites, and it is what
 * makes a swap a one-line change rather than a sweep.
 */
import {
  Ban,
  Bed,
  Bell,
  BellOff,
  BellRing,
  Bike,
  Bomb,
  Bot,
  Brain,
  Building2,
  BusFront,
  Calculator,
  Car,
  ChartColumn,
  ChartLine,
  ChartPie,
  Check,
  Circle,
  ChevronDown,
  CircleCheck,
  Clock,
  Compass,
  Database,
  DoorOpen,
  Download,
  Eraser,
  ExternalLink,
  Eye,
  EyeOff,
  Footprints,
  Gem,
  Globe,
  House,
  Info,
  Key,
  LayoutGrid,
  Link,
  Lock,
  type LucideProps,
  Mail,
  Map,
  MapPin,
  Moon,
  Pencil,
  Plus,
  Pause,
  Pentagon,
  Play,
  RefreshCw,
  Ruler,
  Save,
  ScanSearch,
  Scissors,
  ScrollText,
  Search,
  Send,
  Settings as SettingsCog,
  Shield,
  Square,
  Star,
  Stethoscope,
  StickyNote,
  Sun,
  Tag,
  Target,
  ThumbsUp,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
  Trash2,
  Upload,
  Wallet,
  Wand,
  Wind,
  X,
  Zap,
} from "lucide-react";
import type { ComponentType } from "react";

/** What every icon in this file accepts. `size` takes a number of pixels or any
 *  CSS length, so `size="1.25em"` scales an icon against its own text rather
 *  than against the root font size. */
export type IconProps = LucideProps;

/** The type of an icon, for the components that take one as a prop — an empty
 *  state, a section header, a status row. Written as a component type rather
 *  than as an element so the call site keeps control of the size. */
export type Icon = ComponentType<IconProps>;

/** Sizes that mean something, so a call site picks a role rather than a number.
 *  Everything is relative to the surrounding text: an icon that does not move
 *  when the type scale does is an icon that will be misaligned the first time
 *  the scale changes. */
export const ICON_SIZE = {
  /** Beside a word, in a button or a chip. The default. */
  inline: "1em",
  /** Slightly larger than its label — a section heading, a status row. */
  lead: "1.15em",
  /** The drawing in an empty state, where there is no text to match. */
  display: 48,
} as const;

/** Wrap a lucide icon so it defaults to text size and to `aria-hidden`.
 *
 *  Both defaults are overridable and neither should be: an icon that announces
 *  itself duplicates the label beside it, and an icon sized in pixels stops
 *  tracking the text it belongs to. They are defaults rather than hard-coded
 *  values only because the empty-state drawing genuinely has no text to match. */
function icon(Glyph: Icon, displayName: string): Icon {
  function Wrapped({ size = ICON_SIZE.inline, ...rest }: IconProps) {
    return <Glyph aria-hidden size={size} {...rest} />;
  }
  Wrapped.displayName = displayName;
  return Wrapped;
}

// ── The shell ───────────────────────────────────────────────────────────────
/** The application itself, in the navbar. */
export const Brand = icon(House, "Brand");
/** The properties themselves — the default destination. */
export const Listings = icon(LayoutGrid, "Listings");
/** What the collected properties add up to: health, velocity, price trends. */
export const Insights = icon(ChartPie, "Insights");
/** Something the app will do later, at a known time. */
export const Scheduled = icon(Clock, "Scheduled");
/** Switch the interface language. */
export const Language = icon(Globe, "Language");
/** Switch to the dark theme. */
export const ThemeDark = icon(Moon, "ThemeDark");
/** Switch to the light theme. */
export const ThemeLight = icon(Sun, "ThemeLight");
/** The backend log. */
export const Logs = icon(ScrollText, "Logs");
/** Settings, and the "more filters" disclosure that leads to the same idea. */
export const Cog = icon(SettingsCog, "Cog");
/** Dismiss, clear, remove — never "delete something permanently". */
export const Close = icon(X, "Close");
/** A disclosure that opens downwards. */
export const Disclose = icon(ChevronDown, "Disclose");

// ── A property, and its facts ───────────────────────────────────────────────
/** Where it is. */
export const Place = icon(MapPin, "Place");
/** How big it is. */
export const Area = icon(Ruler, "Area");
/** How many rooms. */
export const Rooms = icon(DoorOpen, "Rooms");
/** How many bedrooms — the portals' own distinction, kept. */
export const Beds = icon(Bed, "Beds");
/** Which floor, and the building it is in. */
export const Floor = icon(Building2, "Floor");
/** The estate agency behind a listing. */
export const Agency = icon(Building2, "Agency");
/** The asking price, where the number needs announcing. */
export const Price = icon(Wallet, "Price");
/** The map, as a place to go. */
export const Atlas = icon(Map, "Atlas");
/** An area drawn by hand on the map. */
export const DrawnArea = icon(Pentagon, "DrawnArea");

// ── What has become of it ───────────────────────────────────────────────────
/** Starred by the user. */
export const Favorite = icon(Star, "Favorite");
/** The price has come down. */
export const PriceDrop = icon(TrendingDown, "PriceDrop");
/** It has gone up — only ever shown against the market, never against a
 *  single listing, which is why it lives beside `PriceDrop` and not with it. */
export const PriceRise = icon(TrendingUp, "PriceRise");
/** Sold, rented out, or the market it belongs to. */
export const Sold = icon(Key, "Sold");
/** Off the portal — not seen for long enough to call it gone. */
export const Gone = icon(Wind, "Gone");
/** Excluded by a keyword the user set. */
export const Filtered = icon(Ban, "Filtered");
/** Discarded by the user, and the action that discards it. */
export const Hidden = icon(EyeOff, "Hidden");
/** Bring a discarded or sold property back. */
export const Restore = icon(Eye, "Restore");
/** The user's own notes on it. */
export const Notes = icon(StickyNote, "Notes");
/** The user's own tags. */
export const Tags = icon(Tag, "Tags");
/** The same home found on more than one portal. */
export const Merged = icon(Link, "Merged");
/** How the app rates the price against the market. */
export const Deal = icon(Target, "Deal");
/** The best end of that rating. */
export const Undervalued = icon(Gem, "Undervalued");
/** The acceptable end of it. */
export const FairPrice = icon(ThumbsUp, "FairPrice");
/** How long it takes to get to work from here. */
export const Commute = icon(BusFront, "Commute");
/** By car. */
export const ByCar = icon(Car, "ByCar");
/** On foot. */
export const OnFoot = icon(Footprints, "OnFoot");
/** By bicycle. */
export const ByBike = icon(Bike, "ByBike");

// ── Searching, and filtering ────────────────────────────────────────────────
/** A monitored search, the thing that goes out to the portals. */
export const Searches = icon(Search, "Searches");
/** Check one listing against the portal, now. */
export const Verify = icon(ScanSearch, "Verify");
/** Describe a search in words. */
export const Describe = icon(Brain, "Describe");
/** Build one field by field. */
export const BuildSearch = icon(Compass, "BuildSearch");
/** Paste a portal URL. */
export const PasteUrl = icon(Link, "PasteUrl");
/** Read the parameters out of a pasted URL. */
export const Extract = icon(Wand, "Extract");
/** Leaves the app — the listing on the portal it came from. */
export const External = icon(ExternalLink, "External");
/** Something worth knowing, offered rather than warned about. */
export const Hint = icon(Info, "Hint");
/** Add another of something — a commute point, a search. */
export const Add = icon(Plus, "Add");
/** Reword a search's description. */
export const Edit = icon(Pencil, "Edit");
/** Remove it for good. */
export const Delete = icon(Trash2, "Delete");
/** Split a merged property back into its listings. */
export const Split = icon(Scissors, "Split");

// ── Being told ──────────────────────────────────────────────────────────────
/** Notifications are on, by some channel. */
export const Notify = icon(Bell, "Notify");
/** Notifications are off for this search. */
export const NotifyOff = icon(BellOff, "NotifyOff");
/** The health alert that fires when a scraper stops working. */
export const Alarm = icon(BellRing, "Alarm");
/** Telegram. */
export const Telegram = icon(Send, "Telegram");
/** Email, as a channel and as an import source. */
export const Email = icon(Mail, "Email");

// ── The machinery ───────────────────────────────────────────────────────────
/** Whether the scrapers are still working. */
export const Health = icon(Stethoscope, "Health");
/** How fast the market is moving. */
export const Velocity = icon(ChartColumn, "Velocity");
/** Where prices are going. */
export const Trend = icon(ChartLine, "Trend");
/** The mortgage and yield calculators. */
export const Calculators = icon(Calculator, "Calculators");
/** Anti-bot settings — how the app keeps being allowed to read. */
export const Bypass = icon(Shield, "Bypass");
/** Fetching a cookie with a real browser, unattended. */
export const Harvester = icon(Bot, "Harvester");
/** A credential. */
export const Credential = icon(Key, "Credential");
/** A one-click install, and anything else that is fast and optional. */
export const Install = icon(Zap, "Install");
/** Start a scan, or put a paused search back to work. */
export const Run = icon(Play, "Run");
/** Stop scanning for now, without deleting anything. */
export const Paused = icon(Pause, "Paused");
/** Run it again — a scan, the backend, a cookie grab. */
export const Restart = icon(RefreshCw, "Restart");
/** A copy of the database. */
export const Backup = icon(Save, "Backup");
/** Take a copy out of the app. */
export const Export = icon(Download, "Export");
/** Bring one back in. */
export const Import = icon(Upload, "Import");
/** Everything the app has stored. */
export const Data = icon(Database, "Data");
/** Clear something that failed, so it can be tried again. */
export const ClearFailed = icon(Eraser, "ClearFailed");
/** The token that guards the API when the bind is widened. */
export const Locked = icon(Lock, "Locked");

// ── States ──────────────────────────────────────────────────────────────────
/** It worked. */
export const Success = icon(CircleCheck, "Success");
/** It needs attention, and the answer may be incomplete. */
export const Warning = icon(TriangleAlert, "Warning");
/** A fact about how the tool works. Never an alarm — see `Warning`. */
export const Note = icon(Info, "Note");
/** Selected, in a checkbox drawn by hand. */
export const Ticked = icon(Check, "Ticked");
/** Not selected. */
export const Unticked = icon(Square, "Unticked");
/** A status light beside a name. Filled at the call site, because an outline
 *  and a fill are two different statuses and only the caller knows which. */
export const Dot = icon(Circle, "Dot");
/** The interface itself broke. */
export const Crashed = icon(Bomb, "Crashed");
/** Nothing to show yet, on the listings grid. */
export const NoResults = icon(House, "NoResults");
/** The listing has no usable photograph. A portal's signed image URL expires
 *  often enough that this is a normal state, not an edge case. */
export const NoImage = icon(House, "NoImage");
