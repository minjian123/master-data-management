<script setup lang="ts">
// 岗位表单页（新建 / 编辑）：`/org/posts/form/:id?`（不进菜单）。
import { PageContainer, SectionContainer } from '@bms/ui-ep'
import { ElButton, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElOption, ElSelect } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { toIdParam, type DeptTreeNode } from '../../domain'
import { ENTITY_STATUS, STATUS_OPTIONS } from '../../domain'
import { isApiAbsent } from '../../runtime'
import { createPost, fetchDeptTree, fetchPost, updatePost } from '../../services/org-service'

defineOptions({ name: 'MdmOrgPostForm' })

const route = useRoute()
const router = useRouter()
const { t } = useOrgI18n()

/** 编辑态标识（空串为新建）。 */
const postId = computed(() => (route.params.id === undefined ? '' : String(route.params.id)))

/** 表单模型（`status` 为普通字符串：值来自契约响应，非字面量联合）。 */
const form = ref<{ code: string; name: string; deptId: string; sort: number; status: string }>({
  code: '',
  name: '',
  deptId: '',
  sort: 0,
  status: ENTITY_STATUS.enabled,
})
const saving = ref(false)
/** 部门候选（树展平）。 */
const deptOptions = ref<{ value: string; label: string }[]>([])

/** 载入表单（部门候选 + 编辑态详情）。 */
async function load(): Promise<void> {
  try {
    const tree = await fetchDeptTree()
    const flat: { value: string; label: string }[] = []
    const walk = (nodes: readonly DeptTreeNode[], depth = 0): void => {
      for (const node of nodes) {
        flat.push({ value: String(node.id), label: `${'　'.repeat(depth)}${node.name}` })
        walk((node.children ?? []) as DeptTreeNode[], depth + 1)
      }
    }
    walk((tree.items ?? []) as DeptTreeNode[])
    deptOptions.value = flat

    if (postId.value !== '') {
      const detail = await fetchPost(postId.value)
      form.value = {
        code: detail.code,
        name: detail.name,
        deptId: String(detail.dept_id),
        sort: detail.sort,
        status: detail.status,
      }
    }
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

/** 保存（新建 / 更新）。 */
async function save(): Promise<void> {
  saving.value = true
  try {
    if (postId.value === '') {
      await createPost({
        code: form.value.code,
        name: form.value.name,
        dept_id: toIdParam(form.value.deptId) as unknown as number,
        sort: form.value.sort,
      })
    } else {
      await updatePost(postId.value, {
        code: form.value.code,
        name: form.value.name,
        dept_id: toIdParam(form.value.deptId),
        sort: form.value.sort,
        status: form.value.status,
      })
    }
    ElMessage.success(t('mdmOrg.common.save'))
    await router.push({ name: 'MdmOrgPostList' })
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  } finally {
    saving.value = false
  }
}

/** 取消返回列表。 */
async function cancel(): Promise<void> {
  await router.push({ name: 'MdmOrgPostList' })
}

onMounted(load)
</script>

<template>
  <page-container :title="postId === '' ? t('mdmOrg.post.form.create') : t('mdmOrg.post.form.edit')">
    <section-container>
      <el-form label-width="120px" data-test="post-form">
        <el-form-item :label="t('mdmOrg.post.form.code')">
          <el-input v-model="form.code" data-test="post-form-code" />
        </el-form-item>
        <el-form-item :label="t('mdmOrg.post.form.name')">
          <el-input v-model="form.name" data-test="post-form-name" />
        </el-form-item>
        <el-form-item :label="t('mdmOrg.post.form.dept')">
          <el-select v-model="form.deptId" data-test="post-form-dept">
            <el-option v-for="item in deptOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('mdmOrg.dept.form.sort')">
          <el-input-number v-model="form.sort" :min="0" data-test="post-form-sort" />
        </el-form-item>
        <el-form-item :label="t('mdmOrg.post.form.status')">
          <el-select v-model="form.status" data-test="post-form-status">
            <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="t(item.labelKey)" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" data-test="post-form-save" @click="save">
            {{ t('mdmOrg.common.save') }}
          </el-button>
          <el-button data-test="post-form-cancel" @click="cancel">{{ t('mdmOrg.common.cancel') }}</el-button>
        </el-form-item>
      </el-form>
    </section-container>
  </page-container>
</template>
