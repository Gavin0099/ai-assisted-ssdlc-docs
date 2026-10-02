"""Portable synthetic reporting inputs: C1 coexistence and auxiliary isolation.

No company corpus, copied findings, network or product repository is required.
"""
import copy

import yaml

from test_report_data_contract import MinimalBundle

AUXILIARY = 'docs/deliverables.md'


def reporting_bundle(root, report_id='synthetic-report'):
    bundle = MinimalBundle(root)
    bundle.data['report_id'] = report_id
    bundle.data['actions'][0]['scope_labels'] = []
    evidence = bundle.action('E-04')
    evidence.update(group='B', kind='合成證據待補', priority=None, priority_reason=None)
    evidence['basis'] = [{'type': 'reviewer_inference', 'rationale': 'Synthetic traceability observation.'}]
    evidence['details'].update({
        '規則依據與效力': '合成 reviewer inference，要求結果可追到對應版本的執行紀錄。',
        '目前哪裡有問題': '合成紀錄尚未提供可追溯引用。',
        '要修改或補什麼': '補上合成測試批次、版本與結果來源。',
        '完成確認方式': '報告能追到相同版本的合成執行紀錄。',
        '修訂句': '請補上 policy.md §release 的測試批次與結果引用；完成後核對相同版本的執行紀錄。'})
    auxiliary = bundle.action('E-13')
    auxiliary.update(kind='合成索引待修', priority='P2', priority_reason='Synthetic index mismatch.')
    auxiliary['locations'] = [{'source_ref': AUXILIARY + '#list', 'source_scope': 'auxiliary', 'display_text': 'Synthetic index §list'}]
    auxiliary['basis'] = [{'type': 'reviewer_inference', 'rationale': 'Synthetic index is separate from corpus.'}]
    auxiliary['details'].update({
        '規則依據與效力': '合成 reviewer inference，只要求輔助索引與引用一致。',
        '目前哪裡有問題': '合成輔助索引的交付項目引用未更新。',
        '要修改或補什麼': '更新 docs/deliverables.md §list 的交付項目引用。',
        '完成確認方式': '輔助索引的引用與合成交付紀錄相符。',
        '修訂句': '請修改 docs/deliverables.md §list 的交付項目引用；完成後核對合成交付紀錄。'})
    bundle.write('auxiliary/index.md', b'Synthetic auxiliary index only.\n')
    bundle.data['auxiliary_sources'] = [{'source_ref': AUXILIARY, 'artifact_ref': bundle.ref('auxiliary/index.md')}]
    bundle.data['actions'].extend([evidence, auxiliary])
    bundle.save()
    target = copy.deepcopy(bundle.assessment)
    target['assessment']['id'] = 'synthetic-machine'
    target['assessment']['target'].update(commit='2' * 40, corpus_digest='3' * 64)
    target['results'][0].update(coverage_verdict='PARTIAL', evidence_strength='medium')
    bundle.write('target.yaml', yaml.safe_dump(target, sort_keys=False).encode())
    bundle.write_json('verification.json', {
        'result': 'not_synced', 'report_data_sha256': bundle.ref('report-data.json')['sha256'],
        'assessment_sha256': bundle.ref('assessment.yaml')['sha256'],
        'target_sha256': bundle.ref('target.yaml')['sha256'], 'evidence_ref': bundle.ref('evidence.txt')})
    bundle.lifecycle = {'report_data_ref': bundle.ref('report-data.json'), 'machine_baseline_ref': None,
                        'review_recommendation': {'opinion': 'CHANGES_REQUESTED', 'reason': 'Synthetic independent review.'},
                        'acceptance_ref': None, 'sync': {'state': 'not_synced', 'target_ref': bundle.ref('target.yaml'),
                                                       'decision_ref': None, 'verification_ref': bundle.ref('verification.json')}}
    bundle.write_json('review-lifecycle.json', bundle.lifecycle)
    return bundle
