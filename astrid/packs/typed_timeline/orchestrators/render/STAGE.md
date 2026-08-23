# typed_timeline.render — Stage

Children: typed_timeline.map then rendering.render (ffmpeg fast-path). Orchestrator admits kernel run+task, invokes mapper to timeline.json/assets.json, ensures tone.wav, validates via match_and_validate, then ffmpeg renders video.mp4. All via sdk.invoke, no second ledger, every run observable.
