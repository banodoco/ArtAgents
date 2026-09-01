"""Generated contract metadata; do not edit by hand.

The source commit and generated-client digest are release metadata.  They make
the vendored transport reproducible without consulting an ambient runtime
checkout at import or test time.
"""

SOURCE_REPOSITORY = "https://github.com/banodoco/banodoco-workspace-runtime.git"
SOURCE_COMMIT = "4050394c5395206f1ec6bf0d905ffbfb7bb0e4de"
GENERATED_CLIENT_SHA256 = "sha256:657c4f56deea2871c46d5f5be4b151256b373405dd559b06a92844efb3eea3ab"

PROTOCOL = "workspace.v1"
COMPONENT_MANIFEST_SHA256 = 'sha256:9e445f9a255a7ae4bc5dbc58d0f77471f252b740e6d3edd97305cbfb35b58d03'
SCHEMA_DIGEST = 'sha256:e86426f871a0ae70359ad43196a8b8c172e8b1d83d6b44d5e45b30fc9ff5c7e2'
OPERATIONS = ('health', 'handshake', 'getRealm', 'doctor', 'createBackup', 'restoreBackup', 'exportRealm', 'tombstoneRealm', 'recoverRealm', 'purgeRealm', 'listProjects', 'createProject', 'getProject', 'updateProject', 'currentProject', 'selectProject', 'listDocuments', 'createDocument', 'getDocument', 'updateDocument', 'listProjectObjects', 'ingestProjectObject', 'listProjectTasks', 'listProjectRuns', 'createTimeline', 'listTimelines', 'createTimelineDocument', 'getTimeline', 'updateTimeline', 'listTimelineHistory', 'diffTimeline', 'archiveTimeline', 'recoverTimeline', 'createShot', 'getShot', 'updateShot', 'archiveShot', 'recoverShot', 'createReference', 'createProjectShot', 'listProjectShots', 'getProjectShot', 'updateProjectShot', 'archiveProjectShot', 'recoverProjectShot', 'addShotItem', 'removeShotItem', 'promoteProjectShotCandidate', 'reorderShotItems', 'listProjectShotTextBindings', 'setProjectShotTextBinding', 'getProjectShotTextBinding', 'setProjectShotTextBindingById', 'rebindProjectShotTextBinding', 'createProjectReference', 'listProjectReferences', 'getProjectReference', 'updateProjectReference', 'archiveProjectReference', 'recoverProjectReference', 'associateReference', 'setPrimaryReference', 'linkReferences', 'getReference', 'updateReference', 'archiveReference', 'recoverReference', 'listMediaRelations', 'createMediaRelation', 'ingestObject', 'getObject', 'headObject', 'admitTask', 'claimTask', 'getTask', 'cancelTask', 'retryTask', 'getRun', 'cancelRun', 'retryRun', 'listRunEvents', 'listEvents', 'registerExecutor', 'listCapabilities', 'registerCapability', 'listGenerations', 'createGeneration', 'getGeneration', 'listVariants', 'createVariant', 'getVariant', 'settleAttempt', 'prepareReboot', 'checkpointAttempt', 'failAttempt', 'heartbeatAttempt', 'requestReboot', 'resumeAttempt')
