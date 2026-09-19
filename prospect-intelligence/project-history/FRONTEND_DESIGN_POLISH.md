# Frontend Visual Design Polish - Complete

## Design Philosophy
**Clean, minimal, professional B2B tool aesthetic** inspired by Stripe Dashboard and Linear.
- Engineering/construction precision
- Trust and reliability
- Not flashy or ornate

## Color Palette

### Primary Colors
- **Background**: White (#ffffff) and off-white (#fafbfc)
- **Text**: Dark slate/charcoal (#1f2937 to #9ca3af)
- **Accent**: Navy/Steel Blue (#1e3a5f) - used sparingly for buttons, links, highlights

### Priority Band Colors (Subtle, not saturated)
- **High**: Green (#057a55) on mint background
- **Medium**: Amber (#b45309) on cream background  
- **Low**: Gray (#6b7280) on light gray background

### Confidence Labels
- **Verified**: Green (#057a55)
- **Probable**: Amber (#b45309)
- **Unverified**: Red (#dc2626)

## Typography

### Font Stack
```css
'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif
```

### Size Scale
- **Body**: 14px (base)
- **Small**: 13px
- **Large**: 16px
- **Headings**: 18-20px
- **Section titles**: 11px uppercase

### Weights
- Body: 400 (normal)
- Headings/labels: 500-600 (medium/semibold)

## Spacing System

### Scale
- 4px, 8px, 12px, 16px, 20px, 24px, 32px, 40px

### Application
- Generous whitespace between sections
- Consistent padding: 24px in cards (16px on mobile)
- Clear visual separation

## Component Styling

### Cards
- White background with light border (#e3e8ed)
- Subtle shadow (0 1px 2px rgba(0,0,0,0.04))
- Border-radius: 8px
- Clean, bordered containers

### Form Inputs
- White background
- Border: #d1d9e0
- Focus: Navy border with light blue glow
- 14px font (16px on mobile for iOS)

### Buttons
- **Primary**: Navy (#1e3a5f) with white text
- **Secondary/Outline**: Transparent with border
- Border-radius: 6px
- Clear visual distinction

### Tabs
- Bottom border style
- Active tab: Navy underline
- Clean, minimal

## Responsive Breakpoints

### Mobile (390px)
```
┌─────────────────────────────┐
│ Coextend Prospect           │
│ Intelligence                │
│ [New Prospect] [API Docs]   │
├─────────────────────────────┤
│                             │
│ ┌─────────────────────────┐ │
│ │ Research a New Prospect │ │
│ │                         │ │
│ │ Company Name *          │ │
│ │ ┌─────────────────────┐ │ │
│ │ │ (full width input)  │ │ │
│ │ └─────────────────────┘ │ │
│ │                         │ │
│ │ Website *               │ │
│ │ ┌─────────────────────┐ │ │
│ │ │                     │ │ │
│ │ └─────────────────────┘ │ │
│ │                         │ │
│ │ ┌─────────────────────┐ │ │
│ │ │   START RESEARCH    │ │ │ ← Full width button
│ │ └─────────────────────┘ │ │
│ └─────────────────────────┘ │
│                             │
│ ┌─────────────────────────┐ │
│ │ How it works            │ │
│ │ 1. Submit...            │ │
│ │ 2. System researches... │ │
│ │ 3. Review brief...      │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘

- Font: 14px
- Cards: 16px padding
- Buttons: Full width
- Inputs: 16px font (iOS friendly)
- Header: Stacked layout
- No horizontal scroll
```

### Tablet (768px+)
```
┌────────────────────────────────────────┐
│ Coextend Prospect Intelligence         │
│                    [New Prospect] [API]│
├────────────────────────────────────────┤
│                                        │
│  ┌────────────────────────────────────┐│
│  │ Research a New Prospect            ││
│  │                                    ││
│  │ Company Name *      Website *      ││
│  │ ┌────────────────┐ ┌──────────────┐││
│  │ │                │ │              │││
│  │ └────────────────┘ └──────────────┘││
│  │                                    ││
│  │ Contact Name (optional)            ││
│  │ ┌──────────────────────────────────┐││
│  │ │                                  │││
│  │ └──────────────────────────────────┘││
│  │                                    ││
│  │       ┌──────────────────┐         ││
│  │       │  START RESEARCH  │         ││
│  │       └──────────────────┘         ││
│  └────────────────────────────────────┘│
│                                        │
└────────────────────────────────────────┘

- Font: 14px base
- Cards: 24px padding
- Buttons: Auto-width
- Header: Horizontal layout
- Max-width: 960px
```

### Desktop (1440px+)
```
┌──────────────────────────────────────────────────────────────┐
│ Coextend Prospect Intelligence        [New Prospect] [API]   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌────────────────────────────────────────────────────────┐ │
│   │ Research a New Prospect                                │ │
│   │                                                        │ │
│   │ Company Name *        Website *        Contact Name    │ │
│   │ ┌──────────────────┐ ┌──────────────┐ ┌──────────────┐ │ │
│   │ │                  │ │              │ │              │ │ │
│   │ └──────────────────┘ └──────────────┘ └──────────────┘ │ │
│   │                                                        │ │
│   │           ┌──────────────────────────┐                 │ │
│   │           │      START RESEARCH      │                 │ │
│   │           └──────────────────────────┘                 │ │
│   └────────────────────────────────────────────────────────┘ │
│                                                              │
│   ┌────────────────────────────────────────────────────────┐ │
│   │ How it works                                           │ │
│   │ 1. Submit a company name and website.                  │ │
│   │ 2. The system researches the prospect...               │ │
│   │ 3. Review the brief, lead score...                     │ │
│   └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘

- Font: 14px base
- Cards: 32px padding
- Max-width: 1100px
- Generous whitespace
- Optimal readability
```

## Results/Brief View

### Score Display
```
┌────────────────────────────────────────────────────────┐
│ Enclos Corp                                            │
│ US · Facade contractor              ┌──────┐  High     │
│                                     │  75  │  ───────  │
│                                     │ /100 │  out of   │
│                                     └──────┘  100      │
└────────────────────────────────────────────────────────┘
```

### Tabs
```
┌─────────┬─────────────┬────────────┬──────────────────┐
│ Brief   │ Lead Score  │ CRM Export │ Outreach Drafts  │
│ ─────── │             │            │                  │
└─────────┴─────────────┴────────────┴──────────────────┘
```

### Brief Sections
Each section in a clean bordered card:
- Company Snapshot
- Contact/Decision-Maker
- Company Research
- Projects & Buying Signals
- Likely Requirements
- Pain-Point Hypotheses
- Recommended Approach
- Risks & Unknowns
- Next Action
- Sources

### Feedback Section
```
┌────────────────────────────────────────────────────────┐
│ Improve Scoring & Briefs — User Feedback               │
│ Help tune our rubric and prompts over time.            │
│                                                        │
│ 1. Was this score accurate?                            │
│    [Too low] [About right ✓] [Too high]               │
│                                                        │
│ 2. How was the brief?                                  │
│    [Poor] [Okay] [Good ✓]                             │
│                                                        │
│ 3. How was the outreach draft?                         │
│    [Poor] [Okay] [Good ✓] [N/A]                       │
│                                                        │
│ Comments (optional)                                    │
│ ┌────────────────────────────────────────────────────┐ │
│ │                                                    │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Your Name (optional)              [Submit Feedback]    │
│ ┌──────────────────────┐                               │
│ │                      │                               │
│ └──────────────────────┘                               │
└────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Light Theme
- Switched from dark (#0f1117) to light (#ffffff/#fafbfc)
- Better readability for professional B2B tools
- Matches Stripe/Linear aesthetic

### 2. Navy Accent
- Primary: #1e3a5f (engineering trust)
- Used sparingly for buttons, links, highlights
- Avoids generic blue (#4f7cff → #1e3a5f)

### 3. Subtle Priority Colors
- High: Green on mint background (not bright green)
- Medium: Amber on cream (not bright yellow)
- Low: Gray on light gray (not red)
- Less saturated, more professional

### 4. Typography Hierarchy
- Single font family: Inter (system fallback)
- Two weights: 400/500 for body, 600 for headings
- 3 sizes max on any screen: 13/14/16px (mobile), 13/14/18px (desktop)

### 5. Generous Whitespace
- Section separation: 24-32px margins
- Card padding: 24px (16px mobile, 32px desktop)
- Form field spacing: 16px gaps

### 6. Responsive Preservation
- All responsive media queries maintained
- Mobile (390px), Tablet (768px), Desktop (1440px)
- No functionality broken

## Files Modified

1. **ui/templates/base.html**
   - Complete CSS redesign
   - New color palette
   - Refined typography
   - Consistent spacing
   - Light theme instead of dark
   - All responsive breakpoints preserved

## Testing Checklist

- [x] Light background with dark text
- [x] Navy accent color applied to buttons/links
- [x] Priority band colors subtle (not saturated)
- [x] Clean sans-serif typography (Inter)
- [x] Generous whitespace between sections
- [x] Simple bordered cards
- [x] Mobile responsive (390px)
- [x] Tablet responsive (768px)
- [x] Desktop responsive (1440px)
- [x] No horizontal scroll on mobile
- [x] Form inputs readable at all sizes
- [x] Buttons with clear primary/secondary distinction
- [x] PWA features still functional
- [x] All existing functionality preserved

## Before/After Comparison

### Before
- Dark theme (#0f1117 background)
- Bright blue accent (#4f7cff)
- Saturated priority colors
- Dense layout
- 10px border radius

### After
- Light theme (#ffffff background)
- Navy accent (#1e3a5f)
- Subtle priority colors
- Generous whitespace
- 6-8px border radius (more refined)
- Professional B2B aesthetic

---

**Status**: ✅ COMPLETE - Ready for user review
