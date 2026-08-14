import os

lines = []
lines.append('import { useEffect, useState, type FormEvent } from "react";')
lines.append('import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";')
lines.append('import { useNavigate, useParams } from "react-router-dom";')
lines.append('import { deleteAsset, getAsset, updateAsset } from "../../api/assets";')
lines.append('import type { AssetCreateInput, AssetStatus } from "../../api/types";')
lines.append('import { MaintenanceRecordsSection } from "../maintenance/MaintenanceRecordsSection";')
lines.append('import { SchedulesSection } from "../schedules/SchedulesSection";')
lines.append('import { ASSET_TYPES } from "./assetTypes";')
lines.append('')

with open('AssetDetailPage.NewView.tsx', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('done')
