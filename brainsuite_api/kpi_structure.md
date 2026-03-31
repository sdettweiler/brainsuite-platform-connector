# ACE Video Analysis - KPI Structure, Logic & Visualizations

## Overview

The **ACE (Advertising Certification Engine)** is a comprehensive video analysis system that evaluates social media video content across multiple dimensions. It uses a pillar-based architecture with sub-KPIs and sophisticated data visualizations to provide detailed assessment of video quality and effectiveness.

---

## Table of Contents

1. [ACE Score & Overall Visualization](#ace-score--overall-visualization)
2. [Pillar Architecture](#pillar-architecture)
3. [Detailed Pillar Analysis with Visualizations](#detailed-pillar-analysis-with-visualizations)
4. [Visualization Types & Interpretation Guide](#visualization-types--interpretation-guide)
5. [Scoring Methodology](#scoring-methodology)

---

## ACE Score & Overall Visualization

### Overall Score Gauge

**Visualization Type:** Circular Gauge (Donut Chart)
- **Range:** 0-100 points
- **Color Coding:**
  - 🟢 Green (67-100): Outer ring filled with vibrant green
  - 🟡 Yellow (34-66): Outer ring filled with orange/gold
  - 🔴 Red (0-33): Outer ring filled with red
- **Current Score:** 54 (shown in large gold text in center)
- **Location:** Executive Summary page, left-center positioning

### Executive Summary Dashboard

**Visualization Type:** Multi-Card Dashboard Layout
- **Components:**
  - Primary video thumbnail (left panel)
  - Large central ACE Score gauge
  - Video content grid (right panel, showing key frames/scenes)
  - Seven pillar cards with individual gauges below main score
  - Pillar icons for visual recognition

**Pillar Score Display Cards:**
Each pillar displays:
- Unique icon (symbol identifying the pillar)
- Pillar name
- Individual score gauge (smaller version of main gauge)
- Color-coded ring based on performance

---

## Pillar Architecture

### 1. **Formal Mandatories** (Compliance & Technical)
**Icon:** ⚠️ Triangle/Alert Symbol  
**Aggregate Score:** 80/100  
**Gauge Color:** 🟡 Yellow/Gold (80 = upper yellow range)

#### Sub-KPIs with Visualizations:

##### **Ideal Aspect Ratio** ✅
- **Visualization Type:** Circular Success Indicator + Platform Comparison Table
  - Green checkmark (✅) or red cross (❌) indicating pass/fail
  - Right panel: Platform-specific aspect ratio reference table
  - Platforms: Facebook Feed, Instagram Feed, TikTok, YouTube In-Stream, Pinterest, etc.
  - Valid Ratios column showing accepted dimensions for each platform
- **Status:** ✅ Green (Video respects YouTube In-Stream guidelines)

##### **Ideal Sound Setting** ✅
- **Visualization Type:** Circular Pass/Fail Indicator + Audio Requirements Table
  - Large green checkmark circle
  - Table showing platform-specific sound requirements
  - Example: YouTube In-Stream = "Video includes sound"
- **Status:** ✅ Green

##### **Scene Pace** ❌
- **Visualization Type:** Numerical Display with Benchmark Comparison
  - Red X circle with "0.2" score
  - Platform comparison table showing benchmark values (0.36 for YouTube In-Stream)
  - Score = 0.2 scenes per second (below 0.36 benchmark)
- **Benchmark Table:** Shows pacing standards for 75th percentile of successful videos
- **Status:** ❌ Red (Below benchmark)

##### **Optimal Length** ✅
- **Visualization Type:** Circular Pass/Fail + Duration Requirements Table
  - Green checkmark circle (100 score)
  - Platform duration guidelines (6-34 seconds depending on platform)
- **Status:** ✅ Green (No limitation for YouTube In-Stream)

##### **Safe Zone** ✅
- **Visualization Type:** Circular Percentage Gauge
  - Green gauge showing 100%
  - Text: "In 100% of scenes, texts are within safe zones"
- **Status:** ✅ Green (100/100)

---

### 2. **Attention** (Viewer Engagement & Focus)
**Icon:** 👁️ Eye Symbol  
**Aggregate Score:** 17/100  
**Gauge Color:** 🔴 Red (17 = critical low performance)

#### Sub-KPIs with Visualizations:

##### **Attention (Eye-Tracking Heatmap)**
- **Visualization Type:** Predictive Eye-Tracking Heat Map Overlay
  - **Left Panel:** Video preview with heatmap overlay
  - **Color Encoding:**
    - 🔴 Red/Warm areas = High viewer attention concentration
    - 🔵 Blue/Cool areas = Low attention zones
    - Green lens/focus markers = Face detection points
  - **Right Panel:** Face detection visualization circles
  - **Interpretation:** Shows temporal attention distribution across video timeline
- **Status:** Qualitative visualization-based analysis

##### **Engaging Beginning** ❌
- **Visualization Type:** Circular Fail Indicator + Demo Video
  - Large red X in circle
  - Red circle outline (fail status)
  - Video preview showing first 2 seconds of content
  - Text feedback: "The beginning of the video (first two seconds) has not enough movement to engage viewers"
- **Status:** ❌ Red (Movement insufficient)

##### **Scene Motion** 🟡
- **Visualization Type:** Partial Circular Gauge + Motion Analysis Chart
  - Semi-filled gauge showing 17/100 (red/yellow)
  - Large "17" in center indicating percentage
  - Graph overlay on video preview showing pixel shift analysis
  - Line chart with white dots on scene, indicating motion metrics per frame
  - Threshold line (dashed orange) showing benchmark level
  - Color coding: < 50 = Red, 50-75 = Yellow, > 75 = Green
- **Status:** 🟡 Yellow (17% of scenes show high motion)

##### **Retention Rate** 📉
- **Visualization Type:** Time-Series Line Graph (Highcharts)
  - **X-Axis:** Time in seconds (0-14+ seconds)
  - **Y-Axis:** % of viewers (0-120)
  - **Line Style:** Orange/gold line with white dot data points
  - **Curve Characteristics:**
    - Starts high at ~100% at 0 seconds (baseline)
    - Shows sharp initial drop (steep downward curve)
    - Continues gradual decline to ~30% by video end
  - **Color Zones:** Labeled as Low (green), Medium (yellow), High (red)
  - **Interpretation:** Sharp drop indicates early viewer loss; gradual decline shows engagement
- **Status:** Quantitative time-series analysis

##### **Perceived Image Brightness** 🟡
- **Visualization Type:** Partial Circular Gauge + Brightness Distribution Chart
  - Yellow gauge showing 67/100
  - "67%" indicating scenes with high perceived brightness
  - Graph overlay on video showing brightness score fluctuation across timeline
  - Blue line with white dots showing brightness variance per scene
  - Threshold benchmark line (dashed orange)
  - Color coding: < 25 = Red, 25-94 = Yellow, > 94 = Green
- **Status:** 🟡 Yellow (67% = moderate brightness)

---

### 3. **Branding** (Brand Recognition & Visibility)
**Icon:** 🏷️ Tag/Label Symbol  
**Aggregate Score:** 0/100  
**Gauge Color:** 🔴 Red (0 = no brand visibility)

#### Sub-KPIs with Visualizations:

##### **Brand Attention** ❌
- **Visualization Type:** Circular Fail Indicator + Brand Detection Video + Score Table
  - Large red circle with "0" in center
  - Video preview with heatmap overlay showing brand attention distribution
  - Table showing brand detection results (Brand column, Score column)
  - Example: Brand "Brand" = 0/100 score
  - Color-coded thresholds: < 25 (red), 25-50 (yellow), > 50 (green)
  - Text: "0% of the scenes have a high brand cut-through"
- **Status:** ❌ Red (0/100 - No brand visibility)

##### **Brand Attention in First Seconds** ❌
- **Visualization Type:** Circular Fail + Video Preview (First 5 seconds)
  - Large red X circle
  - Video preview focused on opening moments
  - Text: "The brand does not attract enough attention in the first 5 seconds"
- **Status:** ❌ Red (Critical - Poor early brand establishment)

##### **Branded Product Attention Over Time** ❌
- **Visualization Type:** Circular Fail + Product Analysis Video
  - Red X indicator
  - Video showing product visibility throughout duration
- **Status:** ❌ Red

##### **Branded Product Attention in First Seconds** ❌
- **Visualization Type:** Circular Fail + Early Product Visibility Video
  - Red X circle
- **Status:** ❌ Red

##### **Brand Name in Voice Over** —
- **Visualization Type:** Gray Neutral Indicator
  - Gray dash (—) indicating N/A status
  - Not applicable to current asset
- **Status:** — (N/A)

---

### 4. **Processing Ease** (Cognitive Load & Comprehension)
**Icon:** 🧠 Brain Symbol  
**Aggregate Score:** 100/100  
**Gauge Color:** 🟢 Green (100 = perfect score)

#### Sub-KPIs with Visualizations:

##### **Ad Recall Potential** ✅
- **Visualization Type:** Circular Success Gauge + Recall Analysis Chart
  - Large green gauge circle showing "100"
  - Video preview with score analysis overlay
  - White-dot line chart showing recall potential across video timeline
  - Chart shows high and stable recall scores throughout
  - Color-coded thresholds: < 50 (red), 50-70 (yellow), > 70 (green)
  - Text: "100% of the scenes have a high ad recall potential"
- **Status:** ✅ Green (100/100 - Excellent memorability)

##### **Visual Simplicity** ✅
- **Visualization Type:** Circular Success Gauge + Simplicity Analysis Chart
  - Large green gauge showing "100"
  - Video preview with overlay analysis
  - Blue-dot line chart showing visual simplicity scores per scene
  - Chart demonstrates consistent high simplicity across timeline
  - Threshold benchmark line (dashed orange)
  - Text: "100% of the scenes have a high degree of visual simplicity"
- **Status:** ✅ Green (100/100 - Clean, uncluttered visuals)

##### **Enough Time to Read** ✅
- **Visualization Type:** Circular Success Gauge + Text Duration Analysis
  - Large green gauge showing "100"
  - Video preview showing on-screen text elements
  - White-dot analysis line across timeline
  - Demonstrates adequate text display duration
- **Status:** ✅ Green (100/100 - Sufficient reading time)

---

### 5. **Emotional Engagement** (Emotional Response & Connection)
**Icon:** 💚 Heart Symbol  
**Aggregate Score:** 100/100  
**Gauge Color:** 🟢 Green (100 = strong emotional connection)

#### Sub-KPIs with Visualizations:

##### **Human Element** ✅
- **Visualization Type:** Circular Gauge + Face Detection Heatmap
  - Green gauge showing "83" (high presence)
  - Video preview with heatmap overlay
  - White circles marking detected human faces/facial features
  - Multiple face detection points across timeline
  - Color-coded thresholds: < 30 (red), 30-70 (yellow), > 70 (green)
  - Text: "The ad incorporates a person in 83% of the scenes"
- **Status:** ✅ Green (83/100 - Strong human presence)

##### **Activation Potential: Visual** ✅
- **Visualization Type:** Large Green Gauge + Visual Arousal Chart
  - Green gauge showing "100" (perfect visual activation)
  - Video preview with emotion analysis overlay
  - White-dot line chart showing visual activation peaks across timeline
  - Chart demonstrates high visual stimulation throughout
  - Multiple peaks indicating moments of high visual engagement
  - Color-coded thresholds: < 33 (red), 33-50 (yellow), > 50 (green)
  - Text: "In 100% of scenes, the visuals have a high activation potential"
- **Status:** ✅ Green (100/100 - Highly stimulating visuals)

##### **Activation Potential: Text** ✅
- **Visualization Type:** Circular Gauge + Text Impact Chart
  - Green gauge showing "83"
  - Video preview with text analysis overlay
  - Graph showing text-based emotional activation per scene
- **Status:** ✅ Green (83/100 - Strong text-based emotion)

---

### 6. **Persuasion** (Call-to-Action & Conversion)
**Icon:** 🛒 Shopping Cart Symbol  
**Aggregate Score:** 25/100  
**Gauge Color:** 🔴 Red (25 = weak persuasive power)

#### Sub-KPIs with Visualizations:

##### **Call-to-Action Attention** ❌
- **Visualization Type:** Circular Fail Indicator
  - Red X circle
  - Text: "Weak CTA visibility"
- **Status:** ❌ Red

##### **Call-to-Action in Voice-Over** —
- **Visualization Type:** Gray Neutral Indicator
  - Gray dash (—)
- **Status:** — (N/A)

##### **Engagement Potential** 🟡
- **Visualization Type:** Circular Semi-Gauge + CTA Effectiveness Chart
  - Orange/yellow gauge showing "50"
  - Moderate engagement potential indicated
- **Status:** 🟡 Yellow (50/100 - Moderate CTA effectiveness)

##### **Fit to Needs: Visual/Text/Voice-Over** —
- **Visualization Type:** Gray Neutral Indicators
  - All showing — (N/A)
- **Status:** — (N/A across all variants)

---

### 7. **Strategic Fit (Unweighted)** (Brand & Campaign Alignment)
**Icon:** 💬 Speech Bubble Symbol  
**Aggregate Score:** N/A  
**Gauge Color:** Gray/Neutral (N/A status)

#### Sub-KPIs with Visualizations:

##### **Fit to Brand Values: Text** —
- **Visualization Type:** Gray Neutral Indicator
- **Status:** — (N/A)

##### **Fit to Brand Values: Visual** —
- **Visualization Type:** Gray Neutral Indicator
- **Status:** — (N/A)

---

## Visualization Types & Interpretation Guide

### 1. **Circular Gauge (Donut Chart)**
- **Appearance:** Partial circle/ring filled with color, number in center
- **Colors:**
  - 🟢 Green ring = 67-100 (excellent)
  - 🟡 Yellow/Gold ring = 34-66 (moderate)
  - 🔴 Red ring = 0-33 (poor)
- **Used For:** Overall scores, pillar scores, individual KPI scores
- **Reading:** Inner number is the score; outer ring color shows performance level

### 2. **Circular Pass/Fail Indicator**
- **Appearance:** Complete circle (✅ or ❌)
- **✅ Green:** Metric meets requirement
- **❌ Red:** Metric fails requirement
- **Used For:** Binary compliance checks (Aspect Ratio, Sound Setting, etc.)

### 3. **Heatmap Overlay**
- **Appearance:** Color gradient overlay on video frame
- **Colors:**
  - 🔴 Red/Warm = High intensity (attention, brightness, or detection)
  - 🟡 Orange/Yellow = Medium intensity
  - 🔵 Blue/Cool = Low intensity
  - Circles/markers = Specific detection points (faces, objects)
- **Used For:** Eye-tracking, brightness analysis, face detection
- **Interpretation:** Warmer colors = areas of viewer focus or detection

### 4. **Time-Series Line Chart (with Highcharts)**
- **Appearance:** Line graph with white dot data points
- **Components:**
  - X-axis: Time in seconds
  - Y-axis: Percentage or score value
  - Orange/blue line: Main metric trend
  - Dashed threshold lines: Benchmark or reference levels
  - White dots: Individual data points per frame
- **Used For:** Retention Rate, motion scores across timeline, brightness variance
- **Reading:** 
  - Sharp drops = Sudden changes (viewer loss, motion spikes)
  - Gradual declines = Natural engagement fade
  - Flat lines = Consistent performance

### 5. **Threshold Color Bands**
- **Appearance:** Color legend below charts showing score ranges
- **Standard Ranges:**
  - Example 1: "< 50" (Red) | "50-75" (Yellow) | "> 75" (Green)
  - Example 2: "< 25" (Red) | "25-94" (Yellow) | "> 94" (Green)
  - Example 3: "< 33" (Red) | "33-50" (Yellow) | "> 50" (Green)
- **Purpose:** Visual guide for interpreting score ranges
- **Used For:** Motion scores, brightness, activation potential, recall potential

### 6. **Video Preview with Overlay Analysis**
- **Appearance:** Video frame with analytical overlay (dots, lines, regions marked)
- **Components:**
  - Background: Current or key video frame
  - Overlay: White dots, lines, or highlighted regions
  - Top-right corner: Scene indicator and time code
  - Text labels: Dimension references (Safe Zone, scene markers)
- **Used For:** All detailed KPI analysis sections
- **Purpose:** Show where in the video the metric is measured

### 7. **Reference Tables**
- **Appearance:** Two-column table with platform/metric names and values
- **Used For:** Aspect ratios, sound settings, optimal lengths, brightness thresholds
- **Purpose:** Provide platform-specific or industry-standard benchmarks

### 8. **Dashboard Multi-Card Layout**
- **Appearance:** Seven individual card sections, each with pillar icon and gauge
- **Components:**
  - Icon (unique symbol for pillar)
  - Pillar name
  - Score gauge
  - Color coding (green/yellow/red)
- **Used For:** Executive Summary overview
- **Purpose:** Quick visual scan of all pillar performance

---

## Visualization Navigation & Structure

### Page Organization

**Left Sidebar Menu:**
- Hierarchical menu with collapsible sections
- Color-coded sections matching pillar themes
- Indented sub-items showing individual KPIs
- Current selection highlighted/expanded

**Main Content Area:**
- Full-width analysis section for selected KPI
- Combination of visualizations (gauge + video + chart)
- Descriptive text and interpretation guidance
- "Learn more" links for detailed documentation

**Video Integration:**
- Embedded HTML5 video player
- Playback controls, timer, quality settings
- Auto-pause on scroll for performance
- Video frames shown as preview backgrounds for heatmaps

---

## Scoring Methodology

### Color-to-Score Mapping

| Visual Indicator | Score Range | Meaning |
|------------------|-------------|---------|
| 🟢 Green | 67-100 | Excellent - exceeds expectations |
| 🟡 Yellow | 34-66 | Moderate - meets basic standards |
| 🔴 Red | 0-33 | Poor - below acceptable threshold |
| ⚪ Gray/— | N/A | Not applicable to this asset |

### Aggregation Logic

**Individual KPI Scoring:**
- ✅ Green KPI = 100 points
- 🟡 Yellow KPI = 50 points
- ❌ Red KPI = 0 points
- — N/A KPI = Excluded from calculation

**Pillar Score Calculation:**
```
Pillar Score = Average of all sub-KPI scores (N/A excluded)
Example: (100 + 100 + 100 + 100 + 0) ÷ 5 = 80
```

**ACE Score Calculation:**
```
ACE Score = Average of all Pillar scores (N/A pillars excluded)
Example: (80 + 17 + 0 + 100 + 100 + 25 + N/A) ÷ 6 = 54
```

---

## Key Performance Indicators Summary Table

| Pillar | Score | Sub-KPIs | Visual Gauge | Purpose |
|--------|-------|----------|--------------|---------|
| Formal Mandatories | 80 | 5 | Yellow | Platform compliance & technical requirements |
| Attention | 17 | 5 | Red | Viewer engagement & focus capture |
| Branding | 0 | 5 | Red | Brand visibility & recognition |
| Processing Ease | 100 | 3 | Green | Cognitive load & comprehension |
| Emotional Engagement | 100 | 3 | Green | Emotional resonance & human connection |
| Persuasion | 25 | 6 | Red | Call-to-action effectiveness |
| Strategic Fit | N/A | 2 | Gray | Brand alignment (N/A for this asset) |
| **ACE Score** | **54** | **31** | **Yellow** | **Overall video effectiveness** |

---

## Visualization Best Practices for Interpretation

### 1. Executive Summary First
- Start with the 7-pillar gauge layout
- Identify red (critical) vs green (strong) areas
- Note N/A (gray) pillars
- Overall ACE score provides context

### 2. Drill into Problem Areas
- Click on red-gauged pillars for detailed analysis
- Review both numerical scores and visual representations
- Cross-reference with video previews
- Check threshold color bands for context

### 3. Use Video Context
- Watch the embedded video to understand findings
- Correlate heatmap hotspots with actual video content
- Note timing of retention rate drops
- Observe brand appearance (or lack thereof) in preview

### 4. Compare Against Benchmarks
- Reference table values show industry/platform standards
- Threshold bands show score ranges
- Dashed lines on charts indicate benchmark levels
- Text explanations confirm whether score is above/below benchmark

### 5. Actionable Insights
- Red scores = Immediate improvement needed
- Yellow scores = Optimization opportunities
- Green scores = Strengths to maintain
- N/A scores = Not measured (skip for now)

---

## Data Visualization Technology Stack

**Chart Libraries Used:**
- Highcharts (for line charts and time-series graphs)
- Custom SVG/Canvas (for heatmaps and overlays)
- HTML5 Video (for preview integration)
- D3.js or similar (for gauge/donut chart rendering)

**Video Analysis Technologies:**
- Predictive eye-tracking AI
- Face detection and emotion recognition
- Pixel-level motion analysis
- Color perception algorithms

---

## Notes for Claude Code Integration

### Visualization Components
- The KPI framework is hierarchical: ACE Score → Pillars → Sub-KPIs
- Visualizations are context-aware (change based on metric type)
- N/A values are intelligently excluded (not treated as 0)
- Scoring uses both binary (pass/fail) and continuous (0-100) metrics

### Data Representations
- Eye-tracking uses predictive AI, not actual viewer data
- Image brightness calculated using human brain perception principles
- Motion/scene analysis uses pixel-level video frame processing
- Retention Rate shows simulated viewer dropout curve

### Platform Awareness
- System is platform-aware: YouTube, Instagram, TikTok, Facebook, Pinterest
- Each platform has different aspect ratio, length, and audio requirements
- Benchmarks reference 75th percentile of successful videos per platform
- Strategic Fit pillar requires brand/campaign-specific data

### Visual Design Principles
- Color-coding is consistent across all visualizations (red/yellow/green)
- Gauges use partial-circle (donut) design for space efficiency
- Heatmaps overlay on actual video content for contextual understanding
- Threshold bands always accompany numerical metrics
- All metrics include interpretive text explaining results

---

## Summary

The ACE Video Analysis system combines sophisticated AI analysis with intuitive data visualization to provide comprehensive video performance assessment. The seven-pillar framework with 31 sub-KPIs, combined with heatmaps, time-series charts, gauges, and video overlays, creates a complete analytical view of video effectiveness. Understanding these visualizations enables stakeholders to quickly identify strengths and improvement opportunities.