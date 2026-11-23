module pulsescan

go 1.26.2

require zycord v0.0.0

require filippo.io/edwards25519 v1.2.0 // indirect

// zycord-node v0.7.1 (commit bc9389b0) checked out next to this folder as ../base
replace zycord => ../base
