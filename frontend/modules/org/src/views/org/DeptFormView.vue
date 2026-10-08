<script setup lang="ts">
// 部门表单页（新建 / 编辑）：`/org/depts/form/:id?`（不进菜单）。
import { PageContainer, SectionContainer } from '@bms/ui-ep'
import { ElButton, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElOption, ElSelect } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { toIdParam, type DeptTreeNode } from '../../domain'
import { ENTITY_STATUS, STATUS_OPTIONS } from '../../domain'
import { isApiAbsent } from '../../runtime'
import { createDept, fetchDept, fetchDeptTree, updateDept } from '../../services/org-service'

defineOptions({ name: 'MdmOrgDeptForm' })

const route = useRoute()
const router = useRouter()
const { t } = useOrgI18n()

/** 编辑态标识（空串为新建）。 */
const deptId = computed(() => (route.params.id === undefined ? '' : String(route.params.id)))

/** 表单模型（`status` 为普通字符串：值来自契约响应，非字面量联合）。 */
const form = ref<{ name: string; parentId: string; sort: number; status: string }>({
  name: '',
  parentId: '',
  sort: 0,
  status: ENTITY_STATUS.enabled,
})
const saving = ref(false)
/** 父级候选（树展平）。 */
const parentOptions = ref<{ value: string; label: string }[]>([])

/** 载入表单（编辑态取详情；新建态预置父级）。 */
async function load(): Promise<void> {
  try {
    const tree = await fetchDeptTree()
    const flat: { value: string; label: string }[] = []
    const walk = (nodes: readonly DeptTreeNode[], depth = 0): void => {
      for (const node of nodes) {
        if (String(node.id) !== deptId.value) {
          flat.push({ value: String(node.id), label: `${'　'.repeat(depth)}${node.name}` })
        }
        walk((node.children ?? []) as DeptTreeNode[], depth + 1)
      }
    }
    walk((tree.items ?? []) as DeptTreeNode[])
    parentOptions.value = flat

    if (deptId.value !== '') {
      const detail = await fetchDept(deptId.value)
      form.value = {
        name: detail.name,
        parentId: detail.parent_id === null || detail.parent_id === undefined ? '' : String(detail.parent_id),
        sort: detail.sort,
        status: detail.status,
      }
    } else {
      const parent = route.query.parent
      form.value.parentId = parent === undefined ? '' : String(parent)
    }
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

/** 保存（新建 / 更新）。 */
async function save(): Promise<void> {
  saving.value = true
  try {
    if (deptId.value === '') {
      await createDept({ name: form.value.name, parent_id: toIdParam(form.value.parentId), sort: form.value.sort })
    } else {
      await updateDept(deptId.value, { name: form.value.name, sort: form.value.sort, status: form.value.status })
    }
    ElMessage.success(t('mdmOrg.common.save'))
    await router.push({ name: 'MdmOrgDeptList' })
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  } finally {
    saving.value = false
  }
}

/** 取消返回列表。 */
async function cancel(): Promise<void> {
  await router.push({ name: 'MdmOrgDeptList' })
}

onMounted(load)
</script>

<template>
  <page-container :title="deptId === '' ? t('mdmOrg.dept.form.create') : t('mdmOrg.dept.form.edit')">
    <section-container>
      <el-form label-width="120px" data-test="dept-form">
        <el-form-item :label="t('mdmOrg.dept.form.name')">
          <el-input v-model="form.name" data-test="dept-form-name" />
        </el-form-item>
        <el-form-item :label="t('mdmOrg.dept.form.parent')">
          <el-select v-model="form.parentId" clearable :placeholder="t('mdmOrg.dept.form.root')" data-test="dept-form-parent">
            <el-option v-for="item in parentOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('mdmOrg.dept.form.sort')">
          <el-input-number v-model="form.sort" :min="0" data-test="dept-form-sort" />
        </el-form-item>
        <el-form-item v-if="deptId !== ''" :label="t('mdmOrg.dept.form.status')">
          <el-select v-model="form.status" data-test="dept-form-status">
            <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="t(item.labelKey)" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" data-test="dept-form-save" @click="save">
            {{ t('mdmOrg.common.save') }}
          </el-button>
          <el-button data-test="dept-form-cancel" @click="cancel">{{ t('mdmOrg.common.cancel') }}</el-button>
        </el-form-item>
      </el-form>
    </section-container>
  </page-container>
</template>
