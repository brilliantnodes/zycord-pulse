// pulsescan v2 (adds the header target, column 6). pulsescan reads Zycord blocks from a node's RPC (/block?height=H&format=ssz), decodes them with
// zycord-node's own core/types (v0.7.1, bc9389b0) and writes one TSV line per block and one per
// certificate. Read-only. Brilliant Nodes, Zycord Pulse dashboard, 22 Nov 2026.
//
// It scans from -from DOWN to -to (newest first), stays under -rate requests per minute so other
// users of the same node keep their share of its 600/min limit, backs off on 429, and resumes:
// heights already in blocks.tsv are skipped.
package main

import (
	"bufio"
	_ "embed"
	"encoding/hex"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"zycord/core/params"
	"zycord/core/types"
)

//go:embed params_mainnet.json
var mainnetParams []byte

func hx(b []byte) string { return "0x" + hex.EncodeToString(b) }

func main() {
	rpc := flag.String("rpc", "http://127.0.0.1:9420", "node RPC base URL")
	from := flag.Int64("from", -1, "first (highest) height; -1 = tip")
	to := flag.Int64("to", 0, "last (lowest) height")
	out := flag.String("out", "pulse", "output directory")
	rate := flag.Int("rate", 240, "max requests per minute")
	maxRun := flag.Duration("max", 9*time.Hour, "stop after this long (resume later)")
	flag.Parse()

	p, err := params.Parse(mainnetParams)
	if err != nil {
		fmt.Fprintln(os.Stderr, "params:", err)
		os.Exit(2)
	}
	if err := os.MkdirAll(*out, 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	cli := &http.Client{Timeout: 20 * time.Second}
	gap := time.Minute / time.Duration(*rate)
	last := time.Time{}
	get := func(path string) ([]byte, int, error) {
		for attempt := 0; ; attempt++ {
			if w := gap - time.Since(last); w > 0 {
				time.Sleep(w)
			}
			last = time.Now()
			resp, err := cli.Get(*rpc + path)
			if err != nil {
				if attempt < 5 {
					time.Sleep(5 * time.Second)
					continue
				}
				return nil, 0, err
			}
			b, _ := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
			resp.Body.Close()
			if resp.StatusCode == http.StatusTooManyRequests && attempt < 30 {
				time.Sleep(15 * time.Second)
				continue
			}
			return b, resp.StatusCode, nil
		}
	}

	tip := *from
	if tip < 0 {
		b, code, err := get("/head")
		if err != nil || code != 200 {
			fmt.Fprintln(os.Stderr, "head:", code, err)
			os.Exit(2)
		}
		s := string(b)
		i := strings.Index(s, `"height":`)
		if i < 0 {
			fmt.Fprintln(os.Stderr, "head: no height")
			os.Exit(2)
		}
		j := i + len(`"height":`)
		k := j
		for k < len(s) && s[k] >= '0' && s[k] <= '9' {
			k++
		}
		tip, _ = strconv.ParseInt(s[j:k], 10, 64)
	}

	done := map[int64]bool{}
	bpath := filepath.Join(*out, "blocks.tsv")
	if f, err := os.Open(bpath); err == nil {
		sc := bufio.NewScanner(f)
		for sc.Scan() {
			if h, err := strconv.ParseInt(strings.SplitN(sc.Text(), "\t", 2)[0], 10, 64); err == nil {
				done[h] = true
			}
		}
		f.Close()
	}
	bf, err := os.OpenFile(bpath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	defer bf.Close()
	cf, err := os.OpenFile(filepath.Join(*out, "certs.tsv"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	defer cf.Close()

	start := time.Now()
	n, fails := 0, 0
	for h := tip; h >= *to; h-- {
		if done[h] {
			continue
		}
		if time.Since(start) > *maxRun {
			fmt.Printf("stopped at height %d after %s (resume later)\n", h, time.Since(start).Round(time.Second))
			break
		}
		raw, code, err := get(fmt.Sprintf("/block?height=%d&format=ssz", h))
		if err != nil || code != 200 {
			fails++
			fmt.Fprintf(os.Stderr, "height %d: code %d err %v %.120s\n", h, code, err, string(raw))
			if fails > 50 {
				fmt.Println("too many failures, stopping")
				break
			}
			continue
		}
		blk, err := types.UnmarshalBlock(raw, p)
		if err != nil {
			fails++
			fmt.Fprintf(os.Stderr, "height %d: decode %v\n", h, err)
			continue
		}
		hd := blk.Header
		fmt.Fprintf(bf, "%d\t%d\t%s\t%d\t%d\t%s\n", hd.Height, hd.Time, hx(hd.EmissionAddr[:]), len(blk.Certs), len(raw), hd.Target.String())
		for _, c := range blk.Certs {
			signers := make([]string, len(c.Sigs))
			for i, s := range c.Sigs {
				signers[i] = hx(s.PubKey[:])
			}
			kind := int(c.Program.Kind)
			var native string = "0"
			var dsts, srcs []string
			acting, target, deploy := "", "", 0
			switch {
			case c.Program.Transfer != nil:
				sum := types.NativeAsset // placeholder to keep the type in scope
				_ = sum
				var tot uint64
				for _, m := range c.Program.Transfer.Moves {
					srcs = append(srcs, hx(m.Src[:]))
					dsts = append(dsts, hx(m.Dst[:]))
					if m.Asset == types.NativeAsset {
						if v, ok := m.Amount.Uint64(); ok {
							tot += v
						}
					}
				}
				native = strconv.FormatUint(tot, 10)
			case c.Program.CEVM != nil:
				acting, target = hx(c.Program.CEVM.Acting[:]), hx(c.Program.CEVM.Target[:])
				var zero types.Address
				if c.Program.CEVM.Target == zero {
					deploy = 1
				}
			case c.Program.Intent != nil:
				acting, target = hx(c.Program.Intent.Acting[:]), hx(c.Program.Intent.Target[:])
			}
			fmt.Fprintf(cf, "%d\t%d\t%s\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%d\n",
				hd.Height, hd.Time, hx(func() []byte { id := c.ID(); return id[:] }()), kind,
				strings.Join(signers, ","), strings.Join(srcs, ","), strings.Join(dsts, ","), native,
				acting, target, deploy)
		}
		n++
		if n%2000 == 0 {
			fmt.Printf("%s scanned %d, at height %d\n", time.Now().Format("15:04:05"), n, h)
		}
	}
	fmt.Printf("done: %d blocks scanned this run, %d failures, %s\n", n, fails, time.Since(start).Round(time.Second))
}
