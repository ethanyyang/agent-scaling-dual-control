# Released trajectories

Every run is one `results.json` in tau2-bench's own format: the task list, and per episode the full message log with per-call token usage (`usage`), the ledger state and termination label written by our agents into each assistant message's `raw_data` (keys `transfer_testing_completion_budget`, `transfer_testing_multi_agent`, `transfer_testing_termination`), the reward and reward basis, cost, trial and seed. The files are the inputs of every analysis script in this repository.

## Download

The archives are on Zenodo (DOI: see the badge in the top-level README; the record id is set in `data/download.sh`). `bash data/download.sh` fetches the twelve archives, checks them against `data/SHA256SUMS`, and unpacks them into `data/simulations/<run>/results.json`; `bash setup.sh` then links each run into `tau2-bench/data/simulations/`, where the scripts expect them. Total download about 240 MB; unpacked about 1.9 GB.

| Archive | Runs | Compressed | What it holds |
|---|---:|---:|---|
| `grid-sas.tar.gz` | 13 | 48 MB | SAS calibration runs of the 13 grid cells (Table 5 SAS column; Table 3). `gate-airline-sas-gemini3flash-...` is both the reproduction gate and the airline x gemini-3-flash SAS. |
| `grid-mas.tar.gz` | 15 | 62 MB | MAS at 4x for the 13 grid cells (Table 5 MAS column) plus the two qwen3.5-9b MAS cells we ran (retail, telecom; sensitivity rows). |
| `r1.tar.gz` | 4 | 15 MB | R1: SAS capped at 1x and MAS at 1x on the two gemini-3.1-flash-lite cells (Section 4.6). |
| `r2.tar.gz` | 6 | 22 MB | R2: SAS and MAS on three airline cells with the benchmark's default simulator gpt-4.1 (Section 4.6). |
| `uncapped.tar.gz` | 3 | 14 MB | Uncapped arm: MAS with no ceiling on the three cells at or below 45% (Table 8, bottom). |
| `rc25.tar.gz` | 2 | 14 MB | Read-call limit check: two telecom MAS cells at r = 25 (Section 4.1). |
| `s2.tar.gz` | 3 | 14 MB | S2, the strong SAS, on three cells (Section 4.7). |
| `local-4b.tar.gz` | 2 | 5 MB | The October-build retail qwen3.5-4b pair: SAS calibration and MAS (Appendix B). The telecom 4b pair is in grid-sas and grid-mas. |
| `gate-and-pilots.tar.gz` | 3 | 4 MB | The gpt-4.1-mini pilot (150 episodes; the 57:1 input ratio, the power simulation's 0.400 anchor, the revert candidates), an early 5-task pilot, and the local telecom 4b pilot. |
| `smokes.tar.gz` | 25 | 5 MB | Every smoke run cited in the paper or the change log: budget-multiple smokes (b1x to b5x), the S2 smokes (v1 and final), the three fix smokes (`-otd-`), and the local-model smokes. |
| `not-in-paper.tar.gz` | 12 | 30 MB | SAS calibration runs of models dropped when the ladder changed (gemini-3.1-pro, gpt-5.4-mini, gpt-5.4-nano, gpt-5). Dated in the change log; not used by any table. |
| `collaborator.tar.gz` | 7 | 11 MB | Runs produced by a collaborator on their own machines: the 9b MAS on airline and retail at a later benchmark commit (the airline file fails the mechanical bars and is not a cell; the retail file is the replication in Section 4.1), the September qwen3.5-4b SAS export (airline, retail, telecom, and a partial October airline run), and the airline qwen3.5-4b MAS of Appendix B. |

## Inventory

One row per `results.json`. Episodes and infrastructure errors come from the run manifest in `results/calibration-manifests/` where we wrote one; collaborator runs have no manifest of ours and are described in `results/COLLABORATOR-RUNS.md`. SHA-256 is of the file as released.

| Archive | Run | Episodes | Infra. errors | Bytes | SHA-256 |
|---|---|---:|---:|---:|---|
| grid-sas | `calib-airline-s1-gemini31flashlite-high-gpt52low-3trials-seed300` |  |  | 23,513,473 | `3fc369bc175940029e51faa1c42c601d0b80f92e1d6e0a38f043b76ce98afeef` |
| grid-sas | `calib-airline-s1-gpt5mini-high-gpt52low-3trials-seed300` | 150 | 0 | 10,451,825 | `0993b01c8c63b425c660aaaf78254984d0998e4da9142ebe199851878a9136bd` |
| grid-sas | `calib-airline-s1-gpt5nano-high-gpt52low-3trials-seed300` | 150 | 0 | 11,049,909 | `a0e882bf6ac0b28e1a57adca7d9ba7834a2f94a79672b1e4782f41a92942d6cd` |
| grid-sas | `calib-retail-s1-gemini31flashlite-high-gpt52low-3trials-seed300` |  |  | 20,400,173 | `0c9c773e46327890e1240603bb1f1bd3b806e9c4a47a5331a5bfec9897265519` |
| grid-sas | `calib-retail-s1-gemini3flash-high-gpt52low-3trials-seed300` |  |  | 19,327,843 | `836e2a05ad11647964c344e9dfa239652b455a0dd06571d146a04a5a7b1ae450` |
| grid-sas | `calib-retail-s1-gpt5mini-high-gpt52low-3trials-seed300` | 150 | 0 | 11,197,789 | `e2bafb2beaa60ff4d5dc8c88e96c8c156c205b37823d5e60067a3d598b2978da` |
| grid-sas | `calib-retail-s1-gpt5nano-high-gpt52low-3trials-seed300` | 150 | 0 | 10,801,073 | `03c84f443dc29e311495ddfdf5fccf873679cda818e46a4d73ae63e7e73ac7c9` |
| grid-sas | `calib-telecom-s1-gemini31flashlite-high-gpt52low-3trials-seed300` |  |  | 31,525,358 | `4c7b844471fcb6cee121bf447730c093941c99bdd66e2c96a098225af6f9c9ae` |
| grid-sas | `calib-telecom-s1-gemini3flash-high-gpt52low-3trials-seed300` |  |  | 39,727,949 | `8447013d0040fb3b0cc623f72492b041bd3aec89302af7e5b7b3403e4603ffa6` |
| grid-sas | `calib-telecom-s1-gpt5mini-high-gpt52low-3trials-seed300` | 150 | 0 | 23,595,558 | `d4be39972133f2bff6a33fdff0d79913bbb06d5b5af2a08069e230bf4464c0d7` |
| grid-sas | `calib-telecom-s1-gpt5nano-high-gpt52low-3trials-seed300` | 150 | 0 | 35,183,932 | `6e0502f5595df8074447ab68849dedbd75827aed41405d303e6459998651d490` |
| grid-sas | `calib-telecom-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300` | 150 | 0 | 26,697,338 | `37957ae5a52222a744c6363a762b43b602545ad5e0ed81f65a6e5bd42f5024c5` |
| grid-sas | `gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300` |  |  | 26,811,814 | `e188ae2d1c160822a42cedfdac430c013ac3e3bff998e9d856c98613a0e38278` |
| grid-mas | `m1-airline-gemini31flashlite-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 26,284,668 | `add017f87781198f80769fbebf2906b1f1b41badea92caf2f5e60911e798dc6c` |
| grid-mas | `m1-airline-gemini3flash-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 38,720,792 | `25ce0f1a08d1f8905b4215e189c1f232ae47d1267ad42971e50c712ea15f5aa8` |
| grid-mas | `m1-airline-gpt5mini-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 48,816,268 | `cb6a587d123e195f078db2fdca4dd6cb1257c4192f99f308709e1f41bf87bce9` |
| grid-mas | `m1-airline-gpt5nano-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 32,713,179 | `2c78311d98aa87b7910b9c7faf18c343241f937638a932fda9193bef121301dc` |
| grid-mas | `m1-retail-gemini31flashlite-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 26,980,651 | `90091f6e17fee8c30f2265d07abe1d2d08982af815992f7effc5cb682fe9833d` |
| grid-mas | `m1-retail-gemini3flash-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 29,217,453 | `15c77ca75c1081bcb7f57cab772efdf024e82f3307c84344728c83472fd344a8` |
| grid-mas | `m1-retail-gpt5mini-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 40,153,633 | `08463f95fd157670b89695a825d53cc02fe61f28aaa1ab9cfef47a7fbbc69e66` |
| grid-mas | `m1-retail-gpt5nano-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 27,334,972 | `68b607c96a280bc297e3ac33e92f6713f1c310687b80437e75b06a2879ef66af` |
| grid-mas | `m1-telecom-gemini31flashlite-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 31,023,722 | `bfccbe8054f488cb4744f02be05ffe7228c23b05ad9880c2c9e24fcaf76a4cb0` |
| grid-mas | `m1-telecom-gemini3flash-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 54,646,952 | `a8f009e07b933d5ce1f62854fa5bd381c360101a3b9b15184e13c119ff8858c6` |
| grid-mas | `m1-telecom-gpt5mini-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 59,814,051 | `df8a293474f3f13c146669d19297608bfb8af6b2ed7bd27bdc114b9affef5803` |
| grid-mas | `m1-telecom-gpt5nano-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 62,890,941 | `f79e262bc686c71b18602a245ed544e73d3a42109cdf5de555469b105d10c903` |
| grid-mas | `m1-telecom-qwen35-4b-q4-ollama-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 35,077,151 | `b08a6b50532877760698fa7a063d1aebc64824438c56762fdb4738a01e34a7bf` |
| grid-mas | `m1-retail-qwen35-9b-openrouter-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 28,539,717 | `8e996370e25e161b4ea00b3d5de37cf7e9f48cf61b0ccd3681cf2a3d036528b6` |
| grid-mas | `m1-telecom-qwen35-9b-openrouter-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 42,216,204 | `cb527921600cfc674f14a90e205877de6c8c01c626b1e6d5287087b99b93a195` |
| r1 | `s1-airline-gemini31flashlite-high-gpt52low-b1x-capb1x-3trials-seed300` | 150 | 0 | 22,413,840 | `7d991117b470cb027285eda09bae17c41c26a595da5e23c11ffaa53f8feaeb62` |
| r1 | `s1-telecom-gemini31flashlite-high-gpt52low-b1x-capb1x-3trials-seed300` | 150 | 0 | 29,744,018 | `0245834f52846fb9194d8ea216d5b5aa98d23c10a97cc1670d000c0fa3a216b8` |
| r1 | `m1-airline-gemini31flashlite-high-gpt52low-b1x-capb1x-3trials-seed300` | 150 | 0 | 14,223,308 | `f6e1fb27ed166608c07e0f3ee1063a99c61d3fba0c3ef8715c90729edca707e6` |
| r1 | `m1-telecom-gemini31flashlite-high-gpt52low-b1x-capb1x-3trials-seed300` | 150 | 0 | 19,361,014 | `e901085bfa19146db48675a6db9b4f3395dcdd47406f03cdf03a04d4047b4b52` |
| r2 | `calib-airline-s1-gemini31flashlite-high-gpt41-3trials-seed300` | 150 | 0 | 23,589,697 | `7ed47c1ee790371e61d1786a12f9ad56f14fdb04908afadb4a8d077556d4c89d` |
| r2 | `calib-airline-s1-gemini3flash-high-gpt41-3trials-seed300` | 150 | 0 | 25,967,875 | `6f96b18a09a57b0b36cdf88d54259c252118dd2120995e3420a24c205147d226` |
| r2 | `calib-airline-s1-gpt5nano-high-gpt41-3trials-seed300` | 150 | 0 | 11,446,214 | `6d4c47a2c9705d2a4fe2189436b1454dd132cc6311d7f8e91882bc6eccf936a5` |
| r2 | `m1-airline-gemini31flashlite-high-gpt41-b4x-capb1x-3trials-seed300` | 150 | 0 | 27,744,693 | `c36474c32a52db3cfc365494056816ea37e0532c5a7c9203090fb5a87eff0bc7` |
| r2 | `m1-airline-gemini3flash-high-gpt41-b4x-capb1x-3trials-seed300` | 150 | 0 | 38,973,066 | `8ff769e2524fed4865ffd4a595890b25648ae4d6fb8a01a75d356a4c1c922c6d` |
| r2 | `m1-airline-gpt5nano-high-gpt41-b4x-capb1x-3trials-seed300` | 150 | 0 | 32,215,866 | `ae12047cd986ae02e04f05a8fb81a24b8ec950c5d54150478562bdf4821f7e97` |
| uncapped | `m1-airline-gpt5nano-high-gpt52low-uncapped-capb1x-3trials-seed300` | 150 | 0 | 52,320,642 | `99986382e7046221d1d4e74d22856b94cbb43307dfe76b6895575216fe6f9ba8` |
| uncapped | `m1-telecom-gemini31flashlite-high-gpt52low-uncapped-capb1x-3trials-seed300` | 150 | 0 | 37,742,024 | `f58a5fcdc8d25de8018b69a886508ebee57711b77bab2134d0865b43e6695f69` |
| uncapped | `m1-telecom-gpt5nano-high-gpt52low-uncapped-capb1x-3trials-seed300` | 150 | 0 | 69,555,451 | `9150e7bbe4d98a51b0ac6c06df789edf4fc62747751e38174d4b03d1edb86d6e` |
| rc25 | `m1-telecom-gemini31flashlite-high-gpt52low-b4x-capb1x-rc25-3trials-seed300` | 150 | 0 | 32,470,329 | `23e35b63c561da93df37b11fe64cca7d8b478c97c6ae59cf57f2685326e108fb` |
| rc25 | `m1-telecom-gemini3flash-high-gpt52low-b4x-capb1x-rc25-3trials-seed300` | 150 | 0 | 61,063,183 | `9c39125844a30deb47be337c2833b8face0a0ed84a5a6c6a94fa2d13357f9a2c` |
| s2 | `s2-airline-gpt5nano-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 32,297,159 | `43a14e1df2d11873cbebb27da30828bb44af9877781cc1d7581ec522135a4c14` |
| s2 | `s2-telecom-gemini31flashlite-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 40,755,752 | `38d0ca788946815eb83bd0b5a3cc2a52f2dfb2ad5e4c627e03793d54dba1100e` |
| s2 | `s2-telecom-gpt5nano-high-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 59,987,921 | `fc997dbaa52aaf4d4200b52c5adaa24e1cb5c0c326f1ee6667a31bbf6930cc38` |
| local-4b | `local-retail-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300` |  |  | 15,386,642 | `3b8fefe355d894d6413d3eae5268dfcfcf228c03d2242d004c80ed90b8a82c1d` |
| local-4b | `m1-retail-qwen35-4b-q4-oct26-ollama-gpt52low-b4x-capb1x-3trials-seed300` | 150 | 0 | 23,121,700 | `41ecd8e6a6a3fc5d5d1be688340ed3e11f6dd9ab58236f27e20d0e704820809b` |
| gate-and-pilots | `exploratory-airline-sas-gpt41mini-full-3trials-seed300` |  |  | 10,702,757 | `0e6a9bb1c33951e3ae51e0d1f32996d8f4d9adf18d9631119f244ba873ac3bd7` |
| gate-and-pilots | `pilot-airline-sas-gpt41mini-seed300` |  |  | 329,965 | `97020b1594352e1e4b383e287fcdb154409d037b3700af16ad84ccbcc88bc59f` |
| gate-and-pilots | `pilot-local-telecom-s1-qwen35-4b-q4-ollama-gpt52low-1trials-seed300` |  |  | 940,529 | `82995d4c3683b200a13fc6331701e3e903a77023555e8cec463e600f98e83657` |
| smokes | `armA-v5-smoke5-m1-telecom-gemini31flashlite-high-gpt52low-b3x-capb1x-1trials-seed300` | 5 | 0 | 1,008,517 | `3602a1327f5688453d562e5a6620fd1a3cecc64d7fe04aed32318f54813628e7` |
| smokes | `pilot1-nobudgetline-smoke5-m1-telecom-gemini31flashlite-high-gpt52low-b1x-1trials-seed300` | 5 | 0 | 706,781 | `6a0e8fcd8cebf3666ec086c6570cef5bc7a931e996e149f75b17a2e1708c6371` |
| smokes | `smoke-airline-s1-gemini31flashlite-high-gpt52low-2tasks` |  |  | 211,511 | `d6dc816b6508f15e6415aa1a739b2be6a171792eb68ff85841c81f5cf5c36c06` |
| smokes | `smoke-gemini3flash-high-gpt52-low` |  |  | 26,882 | `947c29cf1f61863ce5b362008af230a58a36cf48149b0d8a5977d5f2411fe034` |
| smokes | `smoke-gemini3pro-high-gpt52-low` |  |  | 22,196 | `213c1dc2adabea5e69ee6e6390d5e7d576bd9d54df57b61052abd2346c2f3dc9` |
| smokes | `smoke2-gemini3flash-high-gpt52-low` |  |  | 129,439 | `2351f70a994bda9ac506ea8efa385c7b87b9400b6667c31b979e4e956d0ec5c2` |
| smokes | `smoke20-m1-airline-gemini3flash-high-gpt52low-b4x-capb1x-1trials-seed300` | 20 | 0 | 5,261,814 | `72ff88a47d0adf100c002ac8f68d5fe3b518ce92ccb25a11bae5dd276b2874d8` |
| smokes | `smoke20-m1-telecom-gemini31flashlite-high-gpt52low-b4x-capb1x-1trials-seed300` | 20 | 0 | 4,224,625 | `c3ed1268846f09d6c2df89f6565db7377cc515299d2768f2965387f565bb3c91` |
| smokes | `smoke20-m1-telecom-gemini31flashlite-high-gpt52low-b5x-capb1x-1trials-seed300` | 20 | 0 | 4,519,564 | `94b4cfb5292c7e3ac8c039f4408c8e294c965ef7e1a5a542b720ab598c51e603` |
| smokes | `smoke5-m1-airline-gpt5nano-high-gpt52low-b4x-capb1x-otd-1trials-seed300` | 5 | 0 | 831,530 | `8d479e1a4ac3b6c14cfbab201f3fd734d67e6292005ec7f4b06ba169ce63f3aa` |
| smokes | `smoke5-m1-retail-gpt5mini-high-gpt52low-b4x-capb1x-otd-1trials-seed300` | 5 | 0 | 1,350,362 | `0b2d8212aad2740d06fabab175130468476b2b2b73dcacc2e364cb00a88cb5c2` |
| smokes | `smoke5-m1-retail-qwen35-4b-q4-oct26-ollama-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 878,249 | `814548db8a80e4efd1e21016a201ae02139a64043076457b12fc728d1450ff10` |
| smokes | `smoke5-m1-telecom-gemini31flashlite-high-gpt52low-b1x-1trials-seed300` | 5 | 0 | 683,330 | `b8eacb2cb15b54946eb1d361db96c6ab6872f28fe1372db56a43c36981957fde` |
| smokes | `smoke5-m1-telecom-gemini31flashlite-high-gpt52low-b2x-1trials-seed300` | 5 | 0 | 882,094 | `e426a0b1346fc0ea4526aef6f5f8d83a7e545b79a93be0c1147c806cf2bb0c09` |
| smokes | `smoke5-m1-telecom-gemini31flashlite-high-gpt52low-b3x-1trials-seed300` | 5 | 0 | 992,521 | `9207667358077be862fbb062453e4b2809b41bd0ab00fcf79b09855bf6dcb966` |
| smokes | `smoke5-m1-telecom-gemini31flashlite-high-gpt52low-b3x-capb1x-1trials-seed300` | 5 | 0 | 1,008,267 | `fbdb60b780b5e0f82280ae58a9fda3fbf133c63d9691204aa90def20c9875cbf` |
| smokes | `smoke5-m1-telecom-gemini3flash-high-gpt52low-b4x-capb1x-otd-1trials-seed300` | 5 | 0 | 1,909,490 | `7b797e0a9ecfdc439eefe1409db499908bed750570ec9d62a5924da616387392` |
| smokes | `smoke5-m1-telecom-gpt5nano-high-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 778,395 | `5132ec92aa629de75fd7be2adf18df991a77682d6d61c57cafa385b250411fda` |
| smokes | `smoke5-m1-telecom-qwen35-4b-q4-ollama-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 1,507,174 | `6e4ad6fddb2bc2a4e48deace187276806973f868750e3077bdec87a5b08f7b42` |
| smokes | `smoke5-s2-airline-gpt5nano-high-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 922,890 | `dc729ead33051e44d3764b5956e9e3e2a11d4c3e5f9ad80829abae0fc2caaf7e` |
| smokes | `smoke5-s2-telecom-gemini31flashlite-high-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 1,293,294 | `65ea225a7318bbbbdc59f002ae1696d396e450b423dadea36fd85ba997fb6db2` |
| smokes | `smoke5-s2-telecom-gpt5nano-high-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 1,937,722 | `48fcb78d2b11321b37f5adbe2f2da93405459a1088ced98bf2999f24a3aaec06` |
| smokes | `smoke5v1-s2-airline-gpt5nano-high-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 1,222,871 | `c5a800886e2e370449fb3f8581dfe8349fa1028f483a167e55a94b91b9d47c45` |
| smokes | `smoke5v1-s2-telecom-gemini31flashlite-high-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 1,383,121 | `edbf7c50001577401d14ad327501a74acac44dfc3e2bd65ba9523f9375e11697` |
| smokes | `smoke5v1-s2-telecom-gpt5nano-high-gpt52low-b4x-capb1x-1trials-seed300` | 5 | 0 | 2,337,798 | `b96dbc603392748dbba9e725fe15c50235ac0a97cfa2a870e938e858c056b559` |
| not-in-paper | `calib-airline-s1-gemini31pro-high-gpt52low-3trials-seed300` | 150 | 0 | 22,100,745 | `59b347d7e42e5cf6ec3fa62f26b96e7f29f3d04a61c6f6afb2edd81a7c83247f` |
| not-in-paper | `calib-airline-s1-gpt5-high-gpt52low-3trials-seed300` | 150 | 0 | 11,848,485 | `cf78e18aafb1d335506840229809f471eb0692a7f4cc5c51db5e77694446bc20` |
| not-in-paper | `calib-airline-s1-gpt54mini-high-gpt52low-3trials-seed300` | 150 | 0 | 8,786,951 | `91d2871982965595d922fdc1af8e19c63b931783ac58b355ef88ef65bce15487` |
| not-in-paper | `calib-airline-s1-gpt54nano-high-gpt52low-3trials-seed300` | 150 | 0 | 10,444,614 | `d4e3df3377e677622e3b2d4cd14cbd1308e418b3c3cece67d4108e7cd01fb34d` |
| not-in-paper | `calib-retail-s1-gemini31pro-high-gpt52low-3trials-seed300` | 150 | 0 | 18,670,686 | `3e930923e21d85e3594218208ce05c6b3cbeb7cac662ff568f74ded45041b852` |
| not-in-paper | `calib-retail-s1-gpt5-high-gpt52low-3trials-seed300` | 150 | 0 | 10,282,719 | `fc0c8c63de324e276e8a9ccff6d548ec472186f15f5ef267f57a11a5dd0699f0` |
| not-in-paper | `calib-retail-s1-gpt54mini-high-gpt52low-3trials-seed300` | 150 | 0 | 10,425,533 | `44645196138730e882202e2642084ab74b83c91bd6975b0fce47103561779af3` |
| not-in-paper | `calib-retail-s1-gpt54nano-high-gpt52low-3trials-seed300` | 150 | 0 | 10,641,880 | `43c4fc86650802d549885b27ce0948fea53f6fd48f63224de3509fa434fbf069` |
| not-in-paper | `calib-telecom-s1-gemini31pro-high-gpt52low-3trials-seed300` | 150 | 0 | 29,882,065 | `e09de21211cd988192a69516926a14ba4d6b41b7aca8c8dcb882713459c4e11c` |
| not-in-paper | `calib-telecom-s1-gpt5-high-gpt52low-3trials-seed300` | 150 | 0 | 19,016,456 | `eddd64838480025a6a3dd8201d9f830a7aab55a4a7abc4df1275b1ff41a2044f` |
| not-in-paper | `calib-telecom-s1-gpt54mini-high-gpt52low-3trials-seed300` | 150 | 0 | 17,511,547 | `aec8c17baca1b8ca925c1f7f9562b97ac64ae8139a4e10df79c3e9932ab97cbe` |
| not-in-paper | `calib-telecom-s1-gpt54nano-high-gpt52low-3trials-seed300` | 150 | 0 | 20,275,781 | `f18ef31486f30ef898712b98513d676275bb9a54289572821c01eebecdb96d69` |
| collaborator | `qwen35-4b-september-s1-airline-october-partial` |  |  | 1,203,747 | `f5cef3d4a8839ac9dec5bb5c224541708a992882fa2c5825fb45e3c6947f082f` |
| collaborator | `qwen35-4b-september-s1-airline` |  |  | 11,663,346 | `9a82a8ed5fc8bc29d1cba16b633d8aa2722bd47a7d48d3226bdadca616533697` |
| collaborator | `m1-airline-qwen35-4b-q4-ollama-gpt52low-b4x-capb1x-3trials-seed300` |  |  | 24,949,811 | `153f9b2dcf645967e3a103127368392601f764e42d707c98128066b80f9f1232` |
| collaborator | `m1-airline-qwen35-9b-openrouter-high-gpt52low-b4x-capb1x-3trials-seed300` |  |  | 31,936,178 | `85c7e481ec7e1cfdc3337919cb42ca74a4bd8f5051f3b39a928e5d52e72728e5` |
| collaborator | `qwen35-4b-september-s1-telecom` |  |  | 2,227,613 | `32fd8b90b31fb43cee5a95ddb3ebb793a18f1dc741371306806d1f46090d6b14` |
| collaborator | `m1-retail-qwen35-9b-openrouter-high-gpt52low-b4x-capb1x-3trials-seed300` |  |  | 29,518,247 | `27207320d3489f3ec27cde989aa90c484be3aeaf3903c66c4e698309dde44747` |
| collaborator | `qwen35-4b-september-s1-retail` |  |  | 9,017,215 | `1bcf769e8288b9188cf2d808e9f138868a754238994c98e886ba5b35110ec841` |

## Notes

- The local 4-billion runs name the model by its pinned local tag; the build digests are in `ollama/provenance-q4.txt` (registered, September) and `ollama/provenance-q4-2026-10-10-newbuild.txt` (October, used for the retail pair).
- `m1-airline-gemini31flashlite-high-gpt52low-uncapped-*` exists in our working copy as a 158 KB aborted stub; it was never part of the uncapped arm and is not released.
- The void run `void-chatcompletions-calib-airline-s1-gpt54nano-*` (wrong route, superseded the same day) is not released.
- Simulated customers in the trajectories carry the benchmark's synthetic identities (`example.com` addresses). No human took part.
