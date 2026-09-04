"""Generated contract metadata; do not edit by hand.

The source commit and generated-client digest are release metadata.  They make
the vendored transport reproducible without consulting an ambient runtime
checkout at import or test time.
"""

SOURCE_REPOSITORY = "https://github.com/banodoco/banodoco-workspace-runtime.git"
SOURCE_COMMIT = "4050394c5395206f1ec6bf0d905ffbfb7bb0e4de"
# SOURCE_COMMIT is the runtime base. This vendored artifact additionally
# contains the reviewed per-task-storage contract patch from the sibling
# banodoco-workspace-runtime-storage-estimate worktree (2026-09-04).
SOURCE_PATCH = "per-task-storage-estimate@2026-09-04"
GENERATED_CLIENT_SHA256 = "sha256:fac1ea25c8065f090bbaab15a806cfb681abab65ca8d1d843cbb885b6066964a"

PROTOCOL = "workspace.v1"
COMPONENT_MANIFEST_SHA256 = 'sha256:9e445f9a255a7ae4bc5dbc58d0f77471f252b740e6d3edd97305cbfb35b58d03'
SCHEMA_DIGEST = 'sha256:eb9b393bfb489026e221be4adb4af75a5020f5cd7be388d315a9030c9156977d'
OPERATIONS = ('health', 'handshake', 'getRealm', 'doctor', 'createBackup', 'restoreBackup', 'exportRealm', 'tombstoneRealm', 'recoverRealm', 'purgeRealm', 'listProjects', 'createProject', 'getProject', 'updateProject', 'currentProject', 'selectProject', 'listDocuments', 'createDocument', 'getDocument', 'updateDocument', 'listProjectObjects', 'ingestProjectObject', 'listProjectTasks', 'listProjectRuns', 'createTimeline', 'listTimelines', 'createTimelineDocument', 'getTimeline', 'updateTimeline', 'listTimelineHistory', 'diffTimeline', 'archiveTimeline', 'recoverTimeline', 'createShot', 'getShot', 'updateShot', 'archiveShot', 'recoverShot', 'createReference', 'createProjectShot', 'listProjectShots', 'getProjectShot', 'updateProjectShot', 'archiveProjectShot', 'recoverProjectShot', 'addShotItem', 'removeShotItem', 'promoteProjectShotCandidate', 'reorderShotItems', 'listProjectShotTextBindings', 'setProjectShotTextBinding', 'getProjectShotTextBinding', 'setProjectShotTextBindingById', 'rebindProjectShotTextBinding', 'createProjectReference', 'listProjectReferences', 'getProjectReference', 'updateProjectReference', 'archiveProjectReference', 'recoverProjectReference', 'associateReference', 'setPrimaryReference', 'linkReferences', 'getReference', 'updateReference', 'archiveReference', 'recoverReference', 'listMediaRelations', 'createMediaRelation', 'ingestObject', 'getObject', 'headObject', 'admitTask', 'claimTask', 'getTask', 'cancelTask', 'retryTask', 'getRun', 'cancelRun', 'retryRun', 'listRunEvents', 'listEvents', 'registerExecutor', 'listCapabilities', 'registerCapability', 'listGenerations', 'createGeneration', 'getGeneration', 'listVariants', 'createVariant', 'getVariant', 'settleAttempt', 'prepareReboot', 'checkpointAttempt', 'failAttempt', 'heartbeatAttempt', 'requestReboot', 'resumeAttempt')
