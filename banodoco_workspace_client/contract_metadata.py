"""Generated contract metadata; do not edit by hand.

The source commit and generated-client digest are release metadata.  They make
the vendored transport reproducible without consulting an ambient runtime
checkout at import or test time.
"""

SOURCE_REPOSITORY = "https://github.com/banodoco/banodoco-workspace-runtime.git"
SOURCE_COMMIT = "7618aebb754a2d746f459545772487f6364fd677"
GENERATED_CLIENT_SHA256 = "sha256:a3bb45e05e3aeee758f462ff3975745acdde371cfde4e496a0e632978011fc82"

PROTOCOL = "workspace.v1"
COMPONENT_MANIFEST_SHA256 = 'sha256:9e445f9a255a7ae4bc5dbc58d0f77471f252b740e6d3edd97305cbfb35b58d03'
SCHEMA_DIGEST = 'sha256:b5841ab4b66ffe0d5d779bb5acca963bdeada404b3047f8b81258c8c6489a270'
OPERATIONS = ('health', 'handshake', 'getRealm', 'doctor', 'createBackup', 'restoreBackup', 'exportRealm', 'tombstoneRealm', 'recoverRealm', 'purgeRealm', 'listProjects', 'createProject', 'getProject', 'updateProject', 'currentProject', 'selectProject', 'listDocuments', 'createDocument', 'getDocument', 'updateDocument', 'listProjectObjects', 'ingestProjectObject', 'listProjectTasks', 'listProjectRuns', 'createTimeline', 'listTimelines', 'createTimelineDocument', 'getTimeline', 'updateTimeline', 'listTimelineHistory', 'diffTimeline', 'archiveTimeline', 'recoverTimeline', 'createShot', 'getShot', 'updateShot', 'archiveShot', 'recoverShot', 'createReference', 'createProjectShot', 'listProjectShots', 'getProjectShot', 'updateProjectShot', 'archiveProjectShot', 'recoverProjectShot', 'addShotItem', 'removeShotItem', 'reorderShotItems', 'listProjectShotTextBindings', 'setProjectShotTextBinding', 'getProjectShotTextBinding', 'setProjectShotTextBindingById', 'rebindProjectShotTextBinding', 'createProjectReference', 'listProjectReferences', 'getProjectReference', 'updateProjectReference', 'archiveProjectReference', 'recoverProjectReference', 'associateReference', 'setPrimaryReference', 'linkReferences', 'getReference', 'updateReference', 'archiveReference', 'recoverReference', 'listMediaRelations', 'createMediaRelation', 'ingestObject', 'getObject', 'headObject', 'admitTask', 'claimTask', 'getTask', 'cancelTask', 'retryTask', 'getRun', 'cancelRun', 'retryRun', 'listRunEvents', 'listEvents', 'registerExecutor', 'listCapabilities', 'registerCapability', 'listGenerations', 'createGeneration', 'getGeneration', 'listVariants', 'createVariant', 'getVariant', 'settleAttempt', 'prepareReboot', 'checkpointAttempt', 'failAttempt', 'heartbeatAttempt', 'requestReboot', 'resumeAttempt')
