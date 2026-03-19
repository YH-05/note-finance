"""Service layer for youtube_transcript package.

Services
--------
ChannelManager : Channel registration management
Collector : Transcript collection orchestrator
KgExporter : Knowledge graph export (graph-queue JSON generation)
NlmPipeline : NotebookLM source ingestion pipeline
RetryService : FAILED transcript retry service
Scheduler : APScheduler-based periodic collection scheduler
"""
