export interface ChannelSnapshot {
  date: string; // YYYY-MM-DD
  subscribers: number;
  totalViews: number;
  videoCount: number;
}

export interface VideoItem {
  id: string;
  channelId: string;
  channelTitle: string;
  channelHandle: string;
  channelSubscribers: number;
  title: string;
  description: string;
  tags: string[];
  thumbnailUrl: string;
  publishedAt: string;
  durationSeconds: number;
  isShort: boolean;
  views: number;
  likes: number;
  comments: number;
  engagementRate: number; // %: (likes + comments) / views * 100
  viewsPerDay: number;
  outlierScore: number; // multiplier vs channel median views (e.g. 6.4)
  viewsToSubsRatio: number; // multiplier vs channel subscribers (e.g. 3.2)
  estimatedSubConversionScore: number; // 0 - 100 composite score
}

export interface TrackedChannel {
  id: string;
  handle: string;
  title: string;
  description: string;
  thumbnailUrl: string;
  subscribers: number;
  totalViews: number;
  videoCount: number;
  avgViewsRecent: number;
  medianViewsRecent: number;
  engagementRateAvg: number;
  uploadsPlaylistId?: string;
  targetMilestone: number;
  niche: string;
  isDemo?: boolean;
  lastSyncedAt: string;
  snapshots: ChannelSnapshot[];
  recentVideos: VideoItem[];
}

export interface CompetitorChannel {
  id: string;
  handle: string;
  title: string;
  thumbnailUrl: string;
  subscribers: number;
  totalViews: number;
  videoCount: number;
  avgViewsRecent: number;
  medianViewsRecent: number;
  uploadsPlaylistId?: string;
  niche: string;
  isDemo?: boolean;
  lastSyncedAt: string;
  videos: VideoItem[];
}

export interface SubConversionChecklist {
  hook5s: boolean;
  peakValueCta: boolean;
  subConfirmationLink: boolean;
  pinnedCommentCta: boolean;
  endScreenSub: boolean;
}

export interface SavedIdea {
  id: string;
  title: string;
  remakeTitle: string;
  targetKeyword: string;
  sourceVideoId?: string;
  sourceVideoTitle?: string;
  sourceChannelTitle?: string;
  sourceThumbnailUrl?: string;
  sourceOutlierScore?: number;
  format: "short" | "long";
  status: "backlog" | "scripting" | "filming" | "published";
  notes: string;
  tags: string[];
  checklist: SubConversionChecklist;
  createdAt: string;
}

export interface KeywordAnalysisResult {
  keyword: string;
  isLiveData: boolean;
  demandScore: number; // 0 - 100
  opportunityScore: number; // 0 - 100 (higher = easier to break through)
  overallScore: number; // 0 - 100
  verdict: "golden" | "good" | "competitive" | "low_demand";
  avgViews: number;
  medianViews: number;
  smallChannelsInTop10: number;
  shortsRatio: number; // %
  optimalDurationRange: string;
  recommendedTags: string[];
  titlePatterns: string[];
  topVideos: VideoItem[];
}

export interface SeoCheckItem {
  id: string;
  category: "title" | "description" | "tags" | "conversion";
  label: string;
  passed: boolean;
  score: number;
  maxScore: number;
  feedback: string;
  actionTip?: string;
}

export interface SeoAuditResult {
  totalScore: number;
  grade: "S" | "A" | "B" | "C" | "D";
  categoryScores: {
    title: number; // max 30
    description: number; // max 30
    tags: number; // max 20
    conversion: number; // max 20
  };
  checks: SeoCheckItem[];
  suggestedTitles: string[];
  suggestedCtaBlock: string;
  suggestedTags: string[];
}

export interface AiOptimizationResult {
  titles: string[];
  hookScript5s: string;
  seoDescription: string;
  tags: string[];
  subTriggerTip: string;
}

export interface AppSettings {
  youtubeApiKey: string;
  geminiApiKey: string;
  geminiModel?: string;
  googleClientId?: string;
  googleClientSecret?: string;
  defaultCountryCode: string;
  defaultLanguage: string;
}

export interface YoutubeOAuthState {
  refreshToken: string;
  accessToken?: string;
  expiresAt?: number;
  connectedChannelId?: string;
  connectedChannelTitle?: string;
  connectedChannelHandle?: string;
  connectedAt: string;
}

export interface AutopilotLogEntry {
  id: string;
  timestamp: string;
  type: "sync" | "plan" | "publish" | "system";
  message: string;
}

export interface GrowthPlanItem {
  id: string;
  dayLabel: string;
  scheduledDate: string; // YYYY-MM-DD
  vnPublishWindow: string;
  strategyType: "sequel_winner" | "competitor_outlier" | "channel_optimization";
  title: string;
  hook3s: string;
  voiceoverScript: string;
  description?: string;
  tags?: string[];
  pinnedComment: string;
  generatedVideoUrl?: string;
  generatedVideoFileName?: string;
  whySelected: string;
  expectedGoal: string;
  status: "pending" | "in_progress" | "completed";
}

export interface GrowthSprintPlan {
  id: string;
  sprintNumber: number;
  createdAt: string;
  basedOnSubscribers: number;
  basedOnVideoCount: number;
  targetSubscribersGoal: number;
  bestPublishWindowVn: string;
  publishTimingInsight: string;
  strategicSummary: string;
  autoContinueEnabled: boolean;
  items: GrowthPlanItem[];
}

export interface StoreData {
  activeChannelId: string;
  myChannels: TrackedChannel[];
  competitors: CompetitorChannel[];
  ideas: SavedIdea[];
  activePlan?: GrowthSprintPlan | null;
  completedSprintsCount?: number;
  lastAutopilotSyncAt?: string;
  autoSyncOnOpen?: boolean;
  resolvedVideoIds?: string[];
  autopilotLogs?: AutopilotLogEntry[];
  youtubeOAuth?: YoutubeOAuthState | null;
  smartLinkClicks: Record<string, number>;
  settings: AppSettings;
}
